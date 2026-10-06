"""OOXML interpretation-sensitive formatting; annotations never alter source text."""
import json
import xml.etree.ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
FLAGS = ('strike', 'dstrike', 'vanish', 'webHidden', 'highlight')


def value(node, name):
    child = node.find(W + name) if node is not None else None
    if child is None:
        return None
    raw = child.get(W + 'val')
    if name == 'highlight':
        return raw or 'unknown'
    return raw not in ('0', 'false', 'off')


def spans_for(paragraph, node, styles_root, paragraph_text):
    styles = {s.get(W+'styleId'): s for s in styles_root.findall(W+'style')} if styles_root is not None else {}
    defaults = styles_root.find(W+'docDefaults/'+W+'rPrDefault/'+W+'rPr') if styles_root is not None else None
    parents = {id(c): p for p in node.iter() for c in p}
    pstyle = node.find(W+'pPr/'+W+'pStyle')
    paragraph_style = pstyle.get(W+'val') if pstyle is not None else next((sid for sid,s in styles.items() if s.get(W+'type')=='paragraph' and s.get(W+'default') in ('1','true')),None)

    def chain(sid):
        path, seen, unknown = [], set(), []
        while sid:
            if sid in seen or sid not in styles:
                unknown.append('unresolved_style:'+sid);break
            seen.add(sid);s=styles[sid];path.append((sid,s))
            based=s.find(W+'basedOn');sid=based.get(W+'val') if based is not None else None
        return list(reversed(path)),unknown

    spans=[];offset=0
    for run in node.iter(W+'r'):
        ancestor=parents.get(id(run))
        while ancestor is not None and ancestor.tag!=W+'p':ancestor=parents.get(id(ancestor))
        if ancestor is not node:continue
        text=paragraph_text(run);start,end=offset,offset+len(text);offset=end
        direct=run.find(W+'rPr');rstyle=direct.find(W+'rStyle') if direct is not None else None
        layers=[('docDefaults',defaults)];unknown=[]
        for sid in (paragraph_style,rstyle.get(W+'val') if rstyle is not None else None):
            linked,errs=chain(sid);unknown.extend(errs)
            layers.extend(('style:'+name,s.find(W+'rPr')) for name,s in linked)
        p_run_props=node.find(W+'pPr/'+W+'rPr')
        # Paragraph-mark formatting is retained separately, not applied to every text run.
        effective={};provenance={}
        for origin,props in layers:
            for flag in FLAGS:
                v=value(props,flag)
                if v is None:continue
                # OOXML boolean run properties in styles are toggles; direct false overrides.
                if flag!='highlight':
                    if v:effective[flag]=not effective.get(flag,False)
                else:effective[flag]=v
                provenance.setdefault(flag,[]).append({'origin':origin,'value':v})
        for flag in FLAGS:
            v=value(direct,flag)
            if v is not None:
                effective[flag]=v;provenance.setdefault(flag,[]).append({'origin':'direct','value':v})
        wrappers=[];ancestor=parents.get(id(run))
        while ancestor is not None and ancestor is not node:
            if ancestor.tag in (W+'ins',W+'del',W+'moveFrom',W+'moveTo'):
                wrappers.append({'kind':ancestor.tag[len(W):],'attributes':dict(ancestor.attrib)})
            ancestor=parents.get(id(ancestor))
        if effective or unknown or wrappers:
            spans.append({'start':start,'end':end,'text':text,'format':effective,
                          'provenance':provenance,'uncertainties':sorted(set(unknown)),
                          'revisions':wrappers,'requires_visual_check':bool(unknown),
                          'notice':'Formatting is evidence, not a business approval/cancellation decision.'})
    if offset!=len(paragraph['text']) or ''.join(paragraph_text(r) for r in node.iter(W+'r') if
        next((a for a in ancestors(r,parents) if a.tag==W+'p'),None) is node)!=paragraph['text']:
        return [],['run_offsets_do_not_match_original_text; inspect XML and page']
    return spans,[]


def ancestors(node,parents):
    while id(node) in parents:
        node=parents[id(node)];yield node


def visible_annotations(paragraph):
    items=[]
    for span in paragraph.get('formatted_spans',[]):
        f=span['format'];active=[k+'='+str(v) for k,v in f.items()]
        if active or span.get('revisions') or span.get('uncertainties'):
            items.append({'range':[span['start'],span['end']], 'format':f,
                          'revisions':span.get('revisions',[]),'uncertainties':span.get('uncertainties',[])})
    for name in ('format_uncertainties','fields','comment_ids','revisions'):
        if paragraph.get(name):items.append({name:paragraph[name]})
    return items


def markdown_note(paragraph):
    annotations=visible_annotations(paragraph)
    if not annotations:return ''
    return '\n\n> Formatting/interpretation annotations (not source text): '+json.dumps(annotations,ensure_ascii=False)+'\n'
