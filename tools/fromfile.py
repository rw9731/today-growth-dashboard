import json,sys
a=json.load(open(sys.argv[1])); t=''.join(x.get('text','') for x in a)
v,_=json.JSONDecoder().raw_decode(t.strip())
if isinstance(v,str): v=json.loads(v)
json.dump(v,open(sys.argv[2],'w'),ensure_ascii=False); print({k:(val if not isinstance(val,str) or len(val)<80 else len(val)) for k,val in v.items()} if isinstance(v,dict) else len(v))
