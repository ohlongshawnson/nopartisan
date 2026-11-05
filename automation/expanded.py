"""Source-specific, evidence-backed expansion; metadata never enters extension JSON."""
from __future__ import annotations

from collections import Counter
import csv
from datetime import date, datetime
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from . import pipeline as p

STATES = dict(zip(
    'AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split(),
    ['Alabama','Alaska','Arizona','Arkansas','California','Colorado','Connecticut','Delaware','Florida','Georgia',
     'Hawaii','Idaho','Illinois','Indiana','Iowa','Kansas','Kentucky','Louisiana','Maine','Maryland','Massachusetts',
     'Michigan','Minnesota','Mississippi','Missouri','Montana','Nebraska','Nevada','New Hampshire','New Jersey',
     'New Mexico','New York','North Carolina','North Dakota','Ohio','Oklahoma','Oregon','Pennsylvania','Rhode Island',
     'South Carolina','South Dakota','Tennessee','Texas','Utah','Vermont','Virginia','Washington','West Virginia','Wisconsin','Wyoming']))
TERRITORIES = {'American Samoa','Guam','Northern Mariana Islands','Puerto Rico','Virgin Islands'}
APPORTIONMENT = dict(zip(STATES, [7,1,9,4,52,8,5,1,28,14,2,2,17,9,4,4,6,6,2,8,9,13,8,4,8,2,3,4,2,12,3,26,14,1,15,5,6,17,2,7,1,9,38,4,1,11,10,2,8,1]))
PERSON_CATEGORIES = {'senate','house','executive','cabinet','governor'}
TEXT_CATEGORIES = {'party','committee','organization','election_phrase','campaign_phrase','legislative_phrase'}
ACRONYMS = {'dccc','dscc','nrcc','nrsc'}
DEPARTMENTS = {'Secretary of State','Secretary of the Treasury','Secretary of the Interior','Secretary of Agriculture',
               'Secretary of Commerce','Secretary of Labor','Secretary of Health and Human Services',
               'Secretary of Housing and Urban Development','Secretary of Transportation','Secretary of Energy',
               'Secretary of Education','Secretary of Veterans Affairs','Secretary of Homeland Security','Attorney General'}
URLS = {
    'senate_xml': 'https://www.senate.gov/general/contact_information/senators_cfm.xml',
    'congress_csv': 'https://raw.githubusercontent.com/unitedstates/congress-legislators/gh-pages/legislators-current.csv',
    'house_xml': 'https://clerk.house.gov/xml/lists/MemberData.xml',
    'whitehouse_administration': 'https://www.whitehouse.gov/administration/',
    'whitehouse_cabinet': 'https://www.whitehouse.gov/administration/cabinet/',
    'nga_governors': 'https://www.nga.org/governors/',
}


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []

    def all(self, tag=None, cls=None):
        result = []
        for child in self.children:
            if isinstance(child, Node):
                if (tag is None or child.tag == tag) and (cls is None or cls in child.attrs.get('class','').split()):
                    result.append(child)
                result.extend(child.all(tag, cls))
        return result

    def text(self, include_footer=False):
        if self.tag in ('script','style','noscript','nav') or (self.tag=='footer' and not include_footer):
            return ''
        return ' '.join(' '.join(c.text(include_footer) if isinstance(c, Node) else c for c in self.children).split())


class Document(HTMLParser):
    VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}

    def __init__(self, raw):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.current = self.root
        self.feed(raw.decode('utf-8-sig'))
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in self.VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent is not None:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def tokens(value):
    return Counter(re.findall(r'[^\W_]+', p.normalize(value)))


def full_name_parts(value):
    words=re.findall(r'[^\W_]+',p.normalize(value))
    while words and words[-1] in {'jr','sr','ii','iii','iv','vi'}:
        words.pop()
    return [word for word in words if len(word)>1]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def unique(records, key):
    result = {}
    for record in records:
        value = record[key]
        require(value not in result, f'duplicate {key}: {value}')
        result[value] = record
    return result


def candidate_valid(candidate):
    phrase = candidate['phrase']
    category = candidate.get('category', 'person')
    p.phrase_valid(phrase)
    p.phrase_valid(p.normalize(phrase))
    if category in PERSON_CATEGORIES or category == 'person':
        require(not p.blocked_reason(phrase), 'invalid full person name')
        require(len(full_name_parts(phrase))>=2, 'initial-only first name is not a sufficiently specific full name')
    else:
        require(category in TEXT_CATEGORIES, 'unknown keyword category')
        require(len(p.normalize(phrase).split()) >= 2 or p.normalize(phrase) in ACRONYMS,
                'unreviewed single word/acronym')


def config(path):
    cfg = p.load(path)
    require(cfg.get('policy_version') == 2, 'expected expansion policy version 2')
    sources = cfg.get('sources')
    require(isinstance(sources, list) and 8 <= len(sources) <= 32, 'invalid expanded source count')
    unique(sources, 'id')
    kinds = Counter(s['kind'] for s in sources)
    for kind, url in URLS.items():
        require(kinds[kind] == 1, 'missing/duplicate core source: ' + kind)
        require(next(s['url'] for s in sources if s['kind'] == kind) == url, 'unapproved core source URL')
    for source in sources:
        require(re.fullmatch('[a-z][a-z0-9_]{0,39}', source['id']), 'invalid source id')
        p.safe_url(source['url'])
        require(source['required'] is True and source['name'], 'all expanded sources must be required/named')
        require(source['kind'] in {*URLS, 'feed', 'evidence_html'}, 'unknown source kind')
        if source['kind'] == 'evidence_html':
            entries = source.get('entries')
            require(isinstance(entries, list) and 1 <= len(entries) <= 30, 'invalid reviewed evidence entries')
            require(source['checks']['exact_evidence_entries'] == len(entries), 'evidence manifest count differs')
            for entry in entries:
                candidate_valid(entry)
        if source.get('aliases'):
            require(source['kind']=='whitehouse_cabinet', 'biography aliases restricted to reviewed Cabinet roles')
            for alias in source['aliases']:
                p.phrase_valid(alias['for_name'])
                candidate_valid({'phrase':alias['phrase'],'category':'cabinet'})
    cfg['excluded_phrases'] = {p.normalize(k): v for k,v in cfg['excluded_phrases'].items()}
    return cfg


def congress_csv(raw, checks):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
    required = {'bioguide_id','full_name','first_name','last_name','nickname','type','state','party','url'}
    require(required <= set(reader.fieldnames or []), 'missing congressional CSV columns')
    records = []
    for index, row in enumerate(reader):
        require(index < 600 and None not in row and all(v is not None for v in row.values()), 'malformed congressional CSV')
        require(row['type'] in ('sen','rep'), 'unknown congressional office')
        require(re.fullmatch('[A-Z][0-9]{6}', row['bioguide_id']), 'invalid bioguide ID')
        require(row['state'] in {*STATES,'AS','DC','GU','MP','PR','VI'}, 'invalid congressional state')
        for key in ('first_name','last_name','party'):
            p.field(row[key],key)
        if row['full_name']:
            p.field(row['full_name'],'full_name')
        host = urlsplit(p.safe_url(row['url'])).hostname
        require(host.endswith('.senate.gov' if row['type']=='sen' else '.house.gov'), 'nonofficial congressional member URL')
        records.append(row)
    unique(records,'bioguide_id')
    counts = Counter(r['type'] for r in records)
    require(checks['senate_minimum'] <= counts['sen'] <= checks['senate_maximum'], 'CSV Senate count outside bounds')
    require(checks['house_minimum'] <= counts['rep'] <= checks['house_maximum'], 'CSV House count outside bounds')
    return records


def house_xml(raw, checks):
    root = p.xml(raw)
    require(root.tag == 'MemberData', 'unexpected House XML root')
    today = date.today()
    published = datetime.strptime(root.attrib['publish-date'], '%B %d, %Y').date()
    require(0 <= (today-published).days <= checks['max_age_days'], 'House directory stale or future-dated')
    year = today.year - int(today.month == 1 and today.day < 3)
    require(root.findtext('title-info/congress-num') == str((year-1789)//2+1), 'House directory is not the current Congress')
    members = root.findall('members/member')
    expected = {f'{state}{n:02}' for state,count in APPORTIONMENT.items() for n in (range(1,count+1) if count>1 else [0])}
    expected |= {s+'00' for s in ['AQ','DC','GU','MP','PR','VI']}
    codes = [m.findtext('statedistrict') for m in members]
    require(len(codes) == checks['districts'] and len(set(codes)) == len(codes) and set(codes)==expected,
            'House district inventory is incomplete or contains duplicate/unknown districts')
    active, vacancies = [], []
    for member in members:
        info = member.find('member-info')
        identifier = info.findtext('bioguideID')
        district = member.findtext('statedistrict')
        if not identifier:
            require(not info.findtext('official-name') and not info.findtext('firstname'), 'malformed House vacancy')
            vacancies.append(district)
            continue
        require(re.fullmatch('[A-Z][0-9]{6}', identifier), 'invalid House bioguide ID')
        sworn = datetime.strptime(info.find('sworn-date').attrib['date'], '%Y%m%d').date()
        require(sworn <= today, 'House directory includes an unsworn future member')
        first, last, full = (p.field(info.findtext(k), k) for k in ('firstname','lastname','official-name'))
        state = 'AS' if district[:2]=='AQ' else district[:2]
        # namelist is an independently provided, commonly used full name.
        pieces = p.field(info.findtext('namelist'), 'namelist').split(', ',1)
        common = pieces[1]+' '+pieces[0] if len(pieces)==2 else None
        active.append({'identifier':identifier,'first':first,'last':last,'phrase':full,'common':common,
                       'affiliation':{'D':'Democrat','R':'Republican','I':'Independent'}.get(info.findtext('party'),info.findtext('party')),
                       'state':state,'district':district,'official_url':'https://clerk.house.gov/members/'+identifier})
    unique(active,'identifier')
    require(checks['minimum_occupied'] <= len(active) <= 441, 'House occupied-seat count outside bounds')
    return active, {'districts':len(codes),'occupied':len(active),'vacancies':vacancies,'publish_date':published.isoformat()}


def whitehouse(raw, kind, checks):
    root = Document(raw).root
    mains = root.all('main')
    require(len(mains) == 1, 'missing/duplicate White House main content')
    main = mains[0]
    result = []
    if kind == 'whitehouse_administration':
        for h in main.all('h2'):
            for role in ('Vice President','President'):
                if h.text().startswith(role+' '):
                    links = h.all('a')
                    require(len(links)==1, 'invalid executive profile link')
                    href = links[0].attrs['href']
                    require(href.startswith('/administration/'), 'unexpected executive profile URL')
                    result.append({'phrase':h.text()[len(role)+1:], 'role':role,
                                   'official_url':'https://www.whitehouse.gov'+href})
        require(len(result)==checks['exact_count'] and {r['role'] for r in result}==set(checks['roles']),
                'President/VP directory missing or duplicated')
    else:
        # Only adjacent name/role heading pairs inside the same heading group.
        for h in main.all('h2'):
            roles = h.parent.all('h3')
            if len(roles)!=1:
                continue
            role = roles[0].text()
            if not role.startswith(('Secretary of ','Attorney General','Director of ','Administrator of ','United States Trade Representative','Acting ')):
                continue
            result.append({'phrase':h.text(),'role':role,'official_url':URLS[kind]})
        roles = {r['role'].removeprefix('Acting ') for r in result}
        require(checks['minimum'] <= len(result) <= checks['maximum'], 'Cabinet heading count outside bounds')
        require(len(roles)==len(result) and DEPARTMENTS <= roles and bool(roles & {'Secretary of Defense','Secretary of War'}),
                'Cabinet required department/role inventory incomplete')
    for item in result:
        p.phrase_valid(item['phrase'])
        require(not p.blocked_reason(item['phrase']), 'invalid executive name heading')
    return result


def governors(raw, checks):
    root = Document(raw).root
    items = root.all('li','current-governors__item')
    result = []
    for item in items:
        states, links, names = item.all('small','state'), item.all('a'), item.all('div','current-governors__item__link')
        require(len(states)==len(links)==len(names)==1, 'invalid governor directory item')
        state, text = states[0].text(), names[0].text()
        require(text.startswith(state+' Gov. '), 'unexpected governor name prefix')
        name = text[len(state+' Gov. '):]
        url = p.safe_url(links[0].attrs['href'])
        require(url.startswith('https://www.nga.org/governors/'), 'unexpected governor profile source')
        result.append({'state':state,'phrase':name,'profile_url':url})
    by_state = unique(result,'state')
    require(len(result)==checks['exact_count'] and set(STATES.values()) <= by_state.keys(), 'governor state roster incomplete')
    territories = set(by_state)-set(STATES.values())
    # NGA uses "U.S. Virgin Islands" in some directory versions.
    normalized = {s.removeprefix('U.S. ').removeprefix('US ') for s in territories}
    require(len(territories)==checks['territories'] and normalized==TERRITORIES, 'governor territorial roster incomplete')
    return result


def governor_profile(raw, record):
    root = Document(raw).root
    names = [h.text() for h in root.all('h1')]
    states = [h.text() for h in root.all('h5','title__label')]
    require(names==['Gov. '+record['phrase']] and states==[record['state']], 'governor index/profile identity conflict')
    labels = {}
    for item in root.all('li','item'):
        label = item.all('label','label')
        if len(label)==1:
            labels[label[0].text()] = item.text()[len(label[0].text()):].strip()
    require('Current' in labels.get('Terms',''), 'governor profile has no current term')
    current = re.search(r'([A-Za-z]+ \d{1,2}, \d{4})\s*-\s*Current', labels['Terms'])
    require(current and datetime.strptime(current[1],'%B %d, %Y').date() <= date.today(), 'governor term has not started')
    require(labels.get('Party') in {'Democratic','Democrat','Republican','Independent','New Progressive','New Progressive Party','Popular Democratic Party'},
            'missing/unrecognized governor affiliation')
    labels_for_site={"Governor's Website","Governor’s Website","Governer's Website","Government Website","Website"}
    official = [a.attrs['href'] for a in root.all('a') if a.text() in labels_for_site]
    require(len(official)<=1, 'duplicate governor official website links')
    # Some official legacy links are HTTP. Store as evidence only, never request them.
    if official:
        require(urlsplit(official[0]).scheme in {'http','https'} and urlsplit(official[0]).hostname, 'invalid governor website')
    return {'affiliation':{'Democratic':'Democrat'}.get(labels['Party'],labels['Party']),'official_url':official[0] if official else None,'terms':labels['Terms'],
            'website_status':'listed by NGA; not fetched' if official else 'not supplied by NGA profile'}


def collect(cfg, folder):
    fetcher = p.Fetcher()
    sources, parsed, candidates, rejected, feed_entries = [], {}, [], [], []

    def fetch(source, parser):
        record = {**source,'fetched_at':p.now()}
        try:
            raw = fetcher.get(source['url'])
            record.update(sha256=p.digest(raw),bytes=len(raw))
            (folder/(source['id']+'.body')).write_bytes(raw)
            value, checks = parser(raw)
            record.update(status='ok',validation=checks)
            return value
        except Exception as exc:
            record.update(status='failed',error=str(exc))
            raise
        finally:
            sources.append(record)
            p.save(folder/'sources.json',sources)

    def emit(phrase, category, identifier, source_ids, evidence, variant='official', **metadata):
        if not phrase:
            return
        normalized = p.normalize(phrase)
        value = {'phrase':normalized,'category':category,'identifier':identifier,'source_ids':source_ids,
                 'evidence':evidence,'variant':variant,'discovered_at':p.now(),**metadata}
        if category in PERSON_CATEGORIES:
            if len(full_name_parts(normalized))<2:
                rejected.append({**value,'reason':'Initial-only first-name variant withheld; use a supported full given name.'})
                return
        candidate_valid(value)
        if normalized in cfg['excluded_phrases']:
            rejected.append({**value,'reason':cfg['excluded_phrases'][normalized]})
        else:
            candidates.append(value)

    for source in cfg['sources']:
        kind, checks = source['kind'], source.get('checks',{})
        if kind=='senate_xml':
            def parse(raw):
                records=p.parse_source(source,raw)
                require(checks['minimum']<=len(records)<=checks['maximum'],'official Senate count outside bounds')
                require({r['state'] for r in records}==set(STATES),'Senate state coverage incomplete')
                counts=Counter(r['state'] for r in records)
                require(max(counts.values())<=2,'more than two senators for a state')
                return records,{'records':len(records),'states':len(counts)}
        elif kind=='congress_csv':
            def parse(raw):
                records=congress_csv(raw,checks)
                return records,dict(Counter(r['type'] for r in records))
        elif kind=='house_xml':
            parse=lambda raw:house_xml(raw,checks)
        elif kind.startswith('whitehouse_'):
            def parse(raw):
                records=whitehouse(raw,kind,checks)
                text=Document(raw).root.text()
                for alias in source.get('aliases',[]):
                    holder=next((r for r in records if p.normalize(r['phrase'])==p.normalize(alias['for_name'])),None)
                    if holder:
                        require(p.contains(text,alias['phrase']),'reviewed current-holder alias no longer evidenced')
                        holder.setdefault('aliases',[]).append(alias['phrase'])
                    else:
                        rejected.append({'phrase':alias['phrase'],'category':'cabinet','reason':'Reviewed alias holder is no longer in current Cabinet headings.'})
                return records,{'records':len(records),'roles':[r['role'] for r in records],
                                'aliases_verified':sum(len(r.get('aliases',[])) for r in records)}
        elif kind=='nga_governors':
            def parse(raw):
                records=governors(raw,checks)
                return records,{'records':len(records),'states':50,'territories':5}
        elif kind=='feed':
            def parse(raw):
                records=p.parse_source(source,raw)
                require(1<=len(records)<=500,'empty or excessive feed')
                return records,{'entries':len(records),'publication':'discovery only'}
        elif kind=='evidence_html':
            def parse(raw):
                # Self-identification in a publisher's legal footer is valid
                # evidence for an explicitly reviewed organization name.
                text=Document(raw).root.text(include_footer=True)
                require(len(text)>100,'empty or blocked evidence page')
                for entry in source['entries']:
                    require(p.contains(text,entry['phrase']),'reviewed phrase no longer evidenced: '+entry['phrase'])
                return source['entries'],{'evidence_entries':len(source['entries']),'all_literal_phrases_found':True}
        value=fetch(source,parse)
        parsed[kind if kind in URLS else source['id']]=value
        if kind=='feed':
            feed_entries.extend((r,source) for r in value)
        if kind=='evidence_html':
            for entry in value:
                emit(entry['phrase'],entry['category'],source['id']+':'+p.normalize(entry['phrase']),[source['id']],
                     'Reviewed literal political organization/phrase occurs on the identified primary source page.',variant='reviewed literal')

    csv_by_id = unique(parsed['congress_csv'],'bioguide_id')
    for kind, chamber, category in [('senate_xml','sen','senate'),('house_xml','rep','house')]:
        official = unique(parsed[kind],'identifier')
        corroborating = {i:r for i,r in csv_by_id.items() if r['type']==chamber}
        require(official.keys()==corroborating.keys(),category+' membership sets disagree')
        for identifier, person in sorted(official.items()):
            row=corroborating[identifier]
            require(person['state']==row['state'] and person['affiliation']==row['party'],category+' state/affiliation conflict: '+identifier)
            # Some official records have compound names in different fields.
            require(set(tokens(person['last'])) <= set(tokens(row['last_name'])) or
                    tokens(person['phrase'])==tokens(row['full_name']),category+' surname conflict: '+identifier)
            first=next(iter(tokens(person['first'])))
            require(first in tokens(' '.join(row[k] for k in ('first_name','nickname','full_name'))),category+' first-name conflict: '+identifier)
            ids=[next(s['id'] for s in cfg['sources'] if s['kind']==kind),next(s['id'] for s in cfg['sources'] if s['kind']=='congress_csv')]
            meta={'affiliation':person['affiliation'],'state':person['state'],'official_url':person['official_url']}
            official_name=person['phrase']
            if kind=='senate_xml' and re.search(r'\b(?:jr|sr)\.?(?:\s|$)',person['first'],re.I) and p.normalize(official_name)!=p.normalize(row['full_name']):
                rejected.append({'phrase':p.normalize(official_name),'category':category,
                                 'reason':'Official first_name embeds a suffix; assembled first+last has wrong order. Use structured full_name.'})
                official_name=None
            variants=[(official_name,'official directory name'),(person.get('common'),'House namelist'),
                      (row['full_name'],'structured full_name'),
                      (row['first_name']+' '+row['last_name'],'structured first_name + last_name')]
            if row['nickname']:
                variants.append((row['nickname']+' '+row['last_name'],'structured nickname + last_name'))
            for phrase,variant in variants:
                emit(phrase,category,identifier,ids,'Current official membership corroborated by bioguide ID, state, affiliation and name fields.',variant,**meta)

    for kind,category in [('whitehouse_administration','executive'),('whitehouse_cabinet','cabinet')]:
        source_id=next(s['id'] for s in cfg['sources'] if s['kind']==kind)
        for person in parsed[kind]:
            emit(person['phrase'],category,kind+':'+person['role'],[source_id],
                 'Name is paired with current office in the White House directory heading.',role=person['role'],official_url=person['official_url'])
            for alias in person.get('aliases',[]):
                emit(alias,category,kind+':'+person['role'],[source_id],
                     'Current role heading plus reviewed literal full-name alias on the same official page.',
                     variant='reviewed biography alias',role=person['role'],official_url=person['official_url'])

    for governor in parsed['nga_governors']:
        require(re.fullmatch(r'https://www\.nga\.org/governors/[a-z-]+/',governor['profile_url']), 'unsafe governor profile path')
        slug=governor['profile_url'].rstrip('/').rsplit('/',1)[-1]
        profile={'id':'governor_'+slug.replace('-','_'),'kind':'nga_profile','name':'NGA current governor profile: '+governor['state'],
                 'url':governor['profile_url'],'required':True}
        def parse(raw):
            value=governor_profile(raw,governor)
            return value,{'current_term':True,'state':governor['state'],'affiliation':value['affiliation']}
        metadata=fetch(profile,parse)
        emit(governor['phrase'],'governor','governor:'+governor['state'],['governors',profile['id']],
             'NGA current roster and matching profile identify the same governor; term has started and is marked Current.',
             state=governor['state'],**metadata)
        if p.normalize(governor['phrase']) in cfg['excluded_phrases']:
            emit('Gov. '+governor['phrase'],'governor','governor:'+governor['state'],['governors',profile['id']],
                 'Exact current-profile heading includes Gov.; bare name withheld for a documented namesake collision.',
                 variant='literal office-qualified heading',state=governor['state'],**metadata)

    # Deduplicate exact phrases while retaining all supporting records/variants.
    groups={}
    for candidate in candidates:
        groups.setdefault(candidate['phrase'],[]).append(candidate)
    clean, duplicates = [], []
    source_index={s['id']:s for s in sources}
    for phrase, group in sorted(groups.items()):
        identities={r['identifier'] for r in group if r['category'] in PERSON_CATEGORIES}
        if len(identities)>1:
            rejected.append({'phrase':phrase,'category':group[0]['category'],'reason':'Same full name refers to multiple current political identities; withheld.'})
            continue
        result=dict(group[0])
        result['variants']=sorted({r['variant'] for r in group})
        result['source_ids']=sorted({s for r in group for s in r['source_ids']})
        result['provenance']=[{'source_url':source_index[s]['url'],'source_name':source_index[s]['name'],
                               'fetched_at':source_index[s]['fetched_at'],'sha256':source_index[s]['sha256']} for s in result['source_ids']]
        result['ambiguity_concerns']=['Literal full names can match namesakes or nonpolitical stories.'] if result['category'] in PERSON_CATEGORIES else []
        if re.search(r'[".,]',phrase):
            result['ambiguity_concerns'].append('Punctuation/initials are literal; source-backed common variants collected separately.')
        result['news_mentions']=[{'source_name':s['name'],'source_url':s['url'],'article_url':item['url'],
                                  'context':'Validated full phrase occurs in feed title.'} for item,s in feed_entries if p.contains(item['title'],phrase)][:3]
        if len(group)>1:
            duplicates.append({'phrase':phrase,'records':len(group),'variants':result['variants']})
        clean.append(result)

    # Feed discovery is quarantined. Title casing does not establish political identity.
    discovery=[]
    for item,source in feed_entries:
        spans=re.findall(r'\b[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:[ -][A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+){1,3}\b',item['title'])
        for span in spans[:3]:
            if any(p.contains(span,c['phrase']) for c in clean):
                continue
            discovery.append({'phrase':span,'category':'unverified_discovery','source_url':source['url'],
                              'source_name':source['name'],'article_url':item['url'],'discovered_at':p.now(),
                              'evidence':'Title-case span in a news feed title; not political identity evidence.',
                              'review_status':'needs official evidence','publishable':False})
    discovery=list({(p.normalize(r['phrase']),r['article_url']):r for r in discovery}.values())[:40]
    audit={'categories':dict(Counter(c['category'] for c in clean)),'identities':dict(Counter({k:len({c['identifier'] for c in clean if c['category']==k}) for k in PERSON_CATEGORIES})),
           'duplicates':duplicates,'rejected':rejected,'exclusion_policy':cfg['excluded_phrases'],
           'source_count':len(sources),'discovery_candidates':len(discovery)}
    p.save(folder/'collection-audit.json',audit)
    p.save(folder/'discovery.json',discovery)
    p.save(folder/'collected.json',clean)
    require(bool(clean),'empty expanded collection')
    return clean


def write_review(base_raw, candidates, folder):
    existing={p.normalize(x) for x in json.loads(base_raw)['keywords']}
    current={c['phrase'] for c in candidates}
    additions=[c for c in candidates if c['phrase'] not in existing]
    audit=p.load(folder/'collection-audit.json')
    retained=sorted(existing-current)
    result={'added_by_category':dict(Counter(c['category'] for c in additions)),
            'collected_by_category':dict(Counter(c['category'] for c in candidates)),
            'additions':additions,'already_published':len(existing & current),
            'retained_without_current_evidence':retained,'removed':[],
            'stale_review':'Legacy phrases not in this run are flagged, never inferred to be current officeholders or automatically removed.',
            'rejections':audit['rejected'],'duplicates':audit['duplicates'],'discovery_candidates':audit['discovery_candidates']}
    p.save(folder/'categorized-diff.json',result)
    lines=['# Categorized NOpartisan diff','',json.dumps(result['added_by_category'],indent=2),'',
           'No removals. Source failures abort the entire update. Namesakes remain a risk.',
           'News discovery is quarantined and cannot enter the published list.','']
    for category in sorted(result['collected_by_category']):
        lines.extend(['## '+category,''])
        for candidate in additions:
            if candidate['category']==category:
                urls=', '.join(x['source_url'] for x in candidate['provenance'])
                lines.append(f'- {candidate["phrase"]} — {candidate["variant"]}; {urls}')
    lines.extend(['','## Retained legacy phrases without current-run evidence','',*('- '+s for s in retained),
                  '','Review legacy people here for former-office coverage. Retention does not imply current office.',
                  '','## Rejected candidates',''])
    lines.extend('- '+r['phrase']+' — '+r['reason'] for r in audit['rejected'])
    lines.extend(['','Duplicates and all metadata are in categorized-diff.json; source-specific checks in sources.json.',''])
    (folder/'categorized-diff.md').write_text('\n'.join(lines),encoding='utf-8')
    return {k:result[k] for k in ('added_by_category','collected_by_category','already_published','retained_without_current_evidence','discovery_candidates')}
