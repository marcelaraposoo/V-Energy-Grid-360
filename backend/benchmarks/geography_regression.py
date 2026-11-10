"""Avaliação opt-in de nomes parciais/ambíguos pela API real.

Oráculos independentes consultam dim_uc e o agregado mensal em modo somente
leitura. A saída pode conter agregados Gold: manter em .runtime, fora do Git.
"""
import argparse
import json
import math
import sqlite3
import time
import urllib.request
import uuid
from pathlib import Path

from benchmarks.domain_architecture import normalize


# nome, pergunta, operação, referência cadastral, município, ano, grupo de sessão
CASES = [
    ('caetes', 'Qual o consumo de caetés?', 'options', 'Caetés', None, None, 'caetes'),
    ('choice', 'Quero Caetés I, em Abreu e Lima, em 2025.', 'value', 'Caetés I', 'Abreu e Lima', '2025', 'caetes'),
    ('repeat', 'Quero Caetés I, em Abreu e Lima, em 2025.', 'hit', 'Caetés I', 'Abreu e Lima', '2025', 'caetes'),
    ('other_choice', 'Agora Caetés II, no mesmo município e ano.', 'value', 'Caetés II', 'Abreu e Lima', '2025', 'caetes'),
    ('no_accent', 'Quanto foi consumido em caetes?', 'options', 'Caetés', None, None, None),
    ('municipality', 'No município de Caetés, qual foi o consumo?', 'options', 'Caetés', None, None, None),
    ('maranguape', 'Quanto gastou de energia em Maranguape?', 'options', 'Maranguape', None, None, None),
    ('lundgren', 'Consumo do bairro Artur Lundgren?', 'options', 'Artur Lundgren', None, None, None),
    ('serrambi', 'Me mostra o consumo de Serrambi.', 'options', 'Serrambi', None, None, None),
    ('bonanca', 'Qual o consumo de Bonança?', 'options', 'Bonança', None, None, None),
    ('camela', 'E o consumo de Camela?', 'options', 'Camela', None, None, None),
    ('suape', 'Consumo de Suape em 2025?', 'options', 'Suape', None, None, None),
    ('curado', 'Qual o consumo do bairro Curado?', 'options_exact', 'Curado', None, None, None),
    ('bela_vista', 'Qual o consumo de Bela Vista?', 'options_exact', 'Bela Vista', None, None, None),
    ('curado_recife', 'Qual o consumo do bairro Curado em Recife em 2025?', 'value', 'Curado', 'Recife', '2025', None),
    ('prazeres', 'Qual o consumo do bairro Prazeres?', 'value', 'Prazeres', 'Jaboatão dos Guararapes', None, None),
    ('macaxeira', 'Qual o consumo de Macaxeira em 2025?', 'value', 'Macaxeira', 'Recife', '2025', None),
    ('caruaru', 'Qual o consumo do município de Caruaru?', 'uncovered', 'Caruaru', None, None, None),
]


def assess(reply, operation, place, municipality, year, con):
    audit = reply.get('auditoria', {})
    sql = reply.get('sql_executado')
    answer = normalize(reply.get('resposta', ''))
    if operation.startswith('options'):
        operator = 'norm(bairro) = ?' if operation == 'options_exact' else 'instr(norm(bairro), ?) > 0'
        options = con.execute('SELECT DISTINCT municipio,bairro FROM dim_uc WHERE ' + operator,
                              (normalize(place),)).fetchall()
        return (bool(options) and audit.get('resultado') == 'needs_clarification' and not sql
                and all(normalize(m) in answer and normalize(b) in answer for m,b in options)
                and not any(s['codigo']=='C4.3' and s['status']=='completed' for s in audit.get('etapas', [])))
    if operation == 'uncovered':
        absent = con.execute('SELECT COUNT(*) FROM dim_uc WHERE norm(municipio)=?', (normalize(place),)).fetchone()[0] == 0
        return absent and audit.get('resultado')=='needs_clarification' and not sql and 'cadastro' in answer
    if audit.get('resultado') != 'answered' or not sql:
        return False
    conditions = 'municipio=? AND bairro=?'
    parameters = [municipality, place]
    if year:
        conditions += ' AND mes_referencia BETWEEN ? AND ?'
        parameters += [year+'-01',year+'-12']
    expected = con.execute('SELECT SUM(consumo_kwh) FROM fato_segmento_mensal WHERE '+conditions,parameters).fetchone()[0]
    actual = con.execute(sql).fetchall()
    passed = any(type(value) in (int,float) and math.isclose(value,expected,abs_tol=.01)
                 for row in actual for value in row)
    if operation == 'hit':
        passed = passed and audit.get('cache_hit') and not audit.get('tentativas_provedor')
        passed = passed and not any(s['codigo']=='C4.3' and s['status']=='completed' for s in audit.get('etapas', []))
    return bool(passed)


def run(args):
    if not args.allow_provider_calls:
        raise SystemExit('É necessário autorizar chamadas reais com --allow-provider-calls.')
    con=sqlite3.connect(Path(args.gold).resolve().as_uri()+'?mode=ro',uri=True)
    con.execute('PRAGMA query_only=ON')
    con.create_function('norm',1,normalize)
    selected=set(args.cases.split(',')) if args.cases else None
    run_id=uuid.uuid4().hex
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    records=[]
    for name,question,operation,place,municipality,year,group in CASES:
        if selected and name not in selected:
            continue
        started=time.perf_counter()
        record=dict(case=name,question=question,passed=False)
        try:
            payload=json.dumps(dict(pergunta=question,sessao_id=run_id+'-'+(group or name))).encode()
            request=urllib.request.Request(args.url+'/api/ia/perguntar',data=payload,headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(request,timeout=90) as response:
                reply=json.load(response)
            record.update(reply=reply,passed=assess(reply,operation,place,municipality,year,con))
        except Exception as error:
            record['error_type']=type(error).__name__
        record['duration_ms']=round((time.perf_counter()-started)*1000,2)
        records.append(record)
        summary=dict(cases=len(records),passed=sum(r['passed'] for r in records))
        output.write_text(json.dumps(dict(summary=summary,records=records),ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(case=name,passed=record['passed'],ms=record['duration_ms'],
                             answer=record.get('reply',{}).get('resposta')),ensure_ascii=False),flush=True)
    con.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-provider-calls',action='store_true')
    parser.add_argument('--url',default='http://127.0.0.1:8080')
    parser.add_argument('--gold',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--cases')
    run(parser.parse_args())
