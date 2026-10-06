"""Local pre-tokenized index and evidence/attachment one-hop navigation."""
from collections import Counter,defaultdict
import math
import unicodedata


def prepare(documents,tokens):
    postings=defaultdict(dict);frequency=Counter();fields={}
    for doc in documents:
        counters={key:dict(Counter(tokens(value))) for key,value in doc['fields'].items()}
        fields[doc['id']]=counters
        seen=set()
        for field,counts in counters.items():
            for term,count in counts.items():
                postings[term].setdefault(doc['id'],{})[field]=count;seen.add(term)
        frequency.update(seen)
    return {'postings':dict(postings),'frequency':dict(frequency),'field_counts':fields}


def graph(state,manifest):
    edges=defaultdict(list)
    def connect(a,b,reason):
        if a!=b:
            edges[a].append({'target':b,'reason':reason})
            edges[b].append({'target':a,'reason':reason})
    by_owner=defaultdict(list);by_locator=defaultdict(list)
    for u in state['units'].values():
        if u.get('retired'):continue
        by_owner[u['owner_id']].append(u['id'])
        if u['locator'].get('paragraph'):by_locator[(u['owner_id'],u['locator'].get('part'),u['locator']['paragraph'])].append(u['id'])
        if u.get('parent_id'):connect(u['id'],u['parent_id'],'paragraph_context')
    for r in state['records'].values():
        if r['stale_reasons']:continue
        for claim in r['claims']:
            for ref in claim['evidence']:connect(r['id'],ref['unit_id'],'claim_evidence')
        for relation in r.get('relations',[]):connect(r['id'],relation['target_id'],'knowledge_relation:'+relation['kind'])
    for a in manifest['assets']:
        content=a.get('content_source_id')
        children=by_owner.get(content or a['id'],[])
        for occurrence in a['occurrences']:
            loc=occurrence['locator']
            parent_units=list(by_locator.get((occurrence['source_id'],loc.get('part'),loc.get('paragraph')),[]))
            pid=loc.get('paragraph','')
            if pid.startswith('P') and pid[1:].isdigit():
                for neighbour in range(max(1,int(pid[1:])-2),int(pid[1:])+3):
                    parent_units+=by_locator.get((occurrence['source_id'],loc.get('part'),'P'+str(neighbour).zfill(4)),[])
            # Attachment content is structurally related, not automatically semantically equivalent.
            for parent in parent_units:
                for child in children:connect(parent,child,'attachment_occurrence:'+occurrence['id'])
    return {key:list({(e['target'],e['reason']):e for e in values}.values()) for key,values in edges.items()}


def normalize(text):return unicodedata.normalize('NFKC',text).casefold().strip()


def search(index,state,term,tokens,limit,offset,source,section,kind,expand):
    docs={doc['id']:doc for doc in index['documents']}
    eligible={uid for uid,doc in docs.items() if (not source or source in doc['source_ids']) and
              (not section or section.casefold() in doc['section'].casefold()) and (not kind or doc['kind']==kind)}
    original=set(tokens(term,for_query=True));secondary=set();aliases=[]
    for r in state['records'].values():
        if r['stale_reasons'] or (source and source not in r.get('source_ids',[])):continue
        names=[r['name']]+r.get('aliases',[])
        if normalize(term) in {normalize(x) for x in names}:
            # Expand only alternate names. Never expand the whole claim/description.
            secondary.update(t for name in names for t in tokens(name,for_query=True) if t not in original)
            aliases.append({'knowledge_id':r['id'],'names':names,'review_status':r['review_status'],
                            'scope':r['scope'],'notice':'Evidence-bound search aid; does not prove synonym equivalence.'})
    weights={'name':4,'body':2,'section':1.5,'metadata':0.5};scores=defaultdict(float);matches=defaultdict(set)
    for token in original|secondary:
        factor=1 if token in original else .3
        idf=math.log(1+(len(docs)+1)/(index['prepared']['frequency'].get(token,0)+1))
        for uid,fields in index['prepared']['postings'].get(token,{}).items():
            if uid not in eligible:continue
            for field,count in fields.items():
                scores[uid]+=factor*weights[field]*idf*(1+math.log(count));matches[uid].add(token+':'+field)
    phrase=normalize(term)
    for uid in list(scores):
        if any(phrase and phrase in normalize(docs[uid]['fields'][field]) for field in ('name','body')):
            scores[uid]+=5
    related=defaultdict(list)
    if expand=='related':
        seeds=set(scores)
        for uid in sorted(seeds):
            for edge in index['relationships'].get(uid,[]):
                target=edge['target']
                if target not in eligible:continue
                related[target].append({'via':uid,'reason':edge['reason']})
                if target not in seeds:scores[target]=max(scores[target],scores[uid]*.25)
    results=[]
    for uid,score in scores.items():
        doc=docs[uid]
        results.append({k:v for k,v in doc.items() if k!='fields'}|{'score':round(score,5),
            'matches':sorted(matches[uid]),'related_via':related.get(uid,[]),
            'text':doc['fields']['body'][:500],'snippet_truncated':len(doc['fields']['body'])>500})
    results.sort(key=lambda r:(-r['score'],r['id']))
    return {'revision':state['revision'],'query':term,'total_hits':len(results),'offset':offset,
            'results':results[offset:offset+limit], 'next_offset':offset+limit if offset+limit<len(results) else None,
            'alias_expansions':aliases,'expansion':expand,
            'notice':'Related candidates are navigation, not evidence equivalence. Read originals and images before concluding.'}
