"""Seleção independente: não altera nem chama o gerador manual/World Board."""
import hashlib
import time
from datetime import datetime, timedelta
from types import SimpleNamespace, FunctionType
from zoneinfo import ZoneInfo
import mensagens_tibianas
import tibia_info
import zandaobot
import zandaobot_sources
import comandos_tibia
from mensagem_automatica_core import Invalid, SourceUnavailable, FIELDS, EXTRAS, MAX_AGE, UTC, validate, reference_day, fresh

def require_source(data, now, ref, states=()):
    if isinstance(data,dict) and (data.get('velho') or data.get('aguardando') or data.get('estado')=='indisponivel'): raise SourceUnavailable('Fonte temporariamente indisponível.')
    if (not isinstance(data,dict) or data.get('velho') or data.get('aguardando')
        or (states and data.get('estado') not in states)
        or data.get('dia',ref)!=ref): raise Invalid('Fonte selecionada indisponível.')
    stamp=data.get('consulta')
    if not isinstance(stamp,(int,float)) or not -120<=now.timestamp()-stamp<=MAX_AGE: raise Invalid('Fonte selecionada expirada.')
    return stamp

class PublicProvider:
    """Fontes existentes, forçadas; sem aplicar registros pessoais do World Board."""
    def summary(self,c,now):
        selected={key for key,value in c['blocks'].items() if value}
        result={}
        # Consult only selected sources; no news, characters or private World Board state.
        for names,key,collector in [({'calendario'},'calendario',zandaobot_sources.calendar),
                                    ({'yasir','mudancas_online'},'yasir',zandaobot_sources.mini_changes),
                                    ({'dream'},'dream_court',zandaobot_sources.dream_court),
                                    ({'dream_mortes'},'killstatistics',zandaobot.killstatistics)]:
            if selected & names: result[key]=collector(c['mundo'],True)
        if selected & {'criatura','boss'}:
            started=time.time()
            result['boostados']={**tibia_info.boostados(True),'consulta':started}
        return result

    def extra(self,key,arg,c,now):
        # Namespace próprio preserva a formatação existente sem alterar globais do app.
        if not isinstance(getattr(comandos_tibia,'EXTRAS',None),dict) or not callable(getattr(comandos_tibia,'extra',None)):
            raise Invalid('Atualize os módulos de consulta para usar os extras da mensagem automática.')
        namespace=comandos_tibia.__dict__.copy()
        def clone(fn):
            copy=FunctionType(fn.__code__,namespace,fn.__name__,fn.__defaults__,fn.__closure__)
            copy.__kwdefaults__=fn.__kwdefaults__
            return copy
        # Rebind existing bytecode instead of reading .py: compatible with PyInstaller.
        for name,value in list(namespace.items()):
            if isinstance(value,FunctionType) and value.__module__==comandos_tibia.__name__: namespace[name]=clone(value)
        namespace['EXTRAS']={key:(label,clone(fn)) for key,(label,fn) in comandos_tibia.EXTRAS.items()}
        module=SimpleNamespace(**namespace)
        provenance=[]
        def get(cache,endpoint):
            response=zandaobot._consultar(cache,endpoint,True)
            if response.get('velho') or not response.get('dados'): raise SourceUnavailable('Consulta adicional indisponível.')
            stamp=require_source(response,now,reference_day(now))
            provenance.append({'source':'TibiaData','fetched_at':stamp,'reference_date':reference_day(now)})
            return response['dados'],False
        def cached(key,fetch,**kwargs):
            result=fetch()
            if result is None: raise SourceUnavailable('Consulta adicional indisponível.')
            provenance.append({'source':'GuildStats','fetched_at':time.time(),'reference_date':reference_day(now)})
            return {'dados':result,'velho':False}
        module._get=get
        module.sources=SimpleNamespace(cached=cached,get_text=zandaobot_sources.get_text)
        namespace['_get']=module._get;namespace['sources']=module.sources
        output=module.extra(key,arg,c['mundo'],c['personagem'],datetime.fromisoformat(reference_day(now)).date())
        failures=('indisponível','indisponivel','não consegui','informe ','use:','nome inválido','não tem guild')
        if not output or not provenance or any(x in output.casefold() for x in failures): raise SourceUnavailable('Consulta adicional indisponível.')
        return output,provenance

def generate(config,now=None,provider=None):
    now=now or datetime.now(UTC);c=validate(config);provider=provider or PublicProvider();ref=reference_day(now)
    selected={k for k,v in c['blocks'].items() if v}
    remote=selected & {'calendario','yasir','criatura','boss','dream','dream_mortes','mudancas_online'}
    r=provider.summary(c,now) if remote else {}
    sources=[{'source':'local-calculation','fetched_at':now.timestamp(),'reference_date':ref}]
    def source(key,states=()):
        d=r.get(key,{})
        stamp=require_source(d,now,ref,states)
        sources.append({'source':key,'fetched_at':stamp,'reference_date':ref})
        return d
    blocks={};date_label=datetime.fromisoformat(ref).strftime('%d/%m/%Y')
    blocks['dia']='🗓️ '+date_label
    blocks['saudacao']='☀️ Bom dia, '+(c['values'].get('comunidade') if c['fields']['comunidade'] else '')+'!' if c['fields']['comunidade'] and c['values'].get('comunidade') else '☀️ Bom dia, tripulação!'
    position=int.from_bytes(hashlib.sha256((ref+c['personagem']+c['mundo']).encode()).digest()[:4])%len(mensagens_tibianas.MENSAGENS)
    blocks['frase']='💬 Mensagem do dia: '+mensagens_tibianas.MENSAGENS[position]
    blocks['mundo']='🌍 Mundo: '+c['mundo']
    rashid=tibia_info.RASHID[datetime.fromisoformat(ref).weekday()]
    blocks['rashid']='🧳 Rashid: '+rashid
    local=now.astimezone(ZoneInfo('Europe/Berlin'));ss=local.replace(hour=10,minute=0,second=0,microsecond=0)
    if ss<=local: ss=(local+timedelta(days=1)).replace(hour=10,minute=0,second=0,microsecond=0)
    blocks['server_save']='⏰ Próximo SS: '+ss.astimezone(ZoneInfo(c['timezone'] or 'Europe/Berlin')).strftime('%d/%m/%Y às %H:%M')+' ('+(c['timezone'] or 'Europe/Berlin')+')'
    if 'calendario' in selected:
        calendar=source('calendario',('disponivel',));events=calendar.get('eventos')
        if not isinstance(events,list): raise Invalid('Calendário incompleto.')
        active=[e for e in events if e.get('estado')=='ativo']
        blocks['calendario']='\n'.join('🎉 Evento: '+e['titulo']+' (até '+e['fim']+' no SS)' for e in active) or '🎉 Nenhum evento listado no calendário.'
    if selected & {'yasir','mudancas_online'}:
        y=source('yasir',('presente','ausente'))
        if y.get('origem')=='world_board_manual': raise Invalid('World Board manual não permitido.')
        blocks['yasir']='🐪 Yasir: '+('🟢 Ativo' if y['estado']=='presente' else '🔴 Inativo')+' (consulta online)'
        if 'mudancas_online' in selected:
            if y.get('mudancas_velhas') or not isinstance(y.get('mudancas'),list): raise Invalid('Mudanças online indisponíveis.')
            blocks['mudancas_online']='🌍 Outras world changes (consulta online):\n'+('\n'.join('• '+x for x in y['mudancas'] if isinstance(x,str)) or 'Nenhuma listada na consulta online.')
    if selected & {'criatura','boss'}:
        boosted=source('boostados')
        for key,label in [('criatura','⭐ Criatura boostada: '),('boss','👑 Boss boostado: ')]:
            if key in selected:
                name=(boosted.get(key) or {}).get('nome')
                if not name: raise Invalid('Boostado indisponível.')
                blocks[key]=label+name
    if 'dream' in selected:
        dream=source('dream_court',('previsto',))
        if not dream.get('nome'): raise Invalid('Dream Court indisponível.')
        blocks['dream']='🌙 Dream Court: '+dream['nome']+' · rotação prevista'
    if 'dream_mortes' in selected:
        kills=source('killstatistics',('disponivel',));bosses=kills.get('bosses')
        if not bosses or any(type(b.get('last_day_killed')) is not int for b in bosses): raise Invalid('Contagens incompletas.')
        blocks['dream_mortes']='📊 Dream Court — mortes (Last Day): '+ '; '.join(str(b['nome'])+': '+str(b['last_day_killed']) for b in bosses)
    lines=[blocks[k] for k in c['blocks'] if c['blocks'][k]]
    for key,label in FIELDS.items():
        if not c['fields'][key] or key=='comunidade' and 'saudacao' in selected: continue
        value=c['values'].get(key,'')
        if not value: raise Invalid('Preencha a variável selecionada.')
        if key not in ('comunidade','assinatura') and c['manualDate']!=ref: raise Invalid('Confirme a data dos valores manuais.')
        lines.append(label+': '+value)
    if c['fields']['comunidade'] and not c['values'].get('comunidade'): raise Invalid('Preencha a comunidade.')
    for key in EXTRAS:
        if c['extras'][key]:
            text,metadata=provider.extra(key,c['args'].get(key,''),c,now);lines.append(text);sources.extend(metadata)
    result={'text':'\n\n'.join(lines),'sources':sources,'reference_date':ref,'generated_at':now.timestamp()}
    if len(result['text'])>16000: raise Invalid('Mensagem excede o limite de tamanho.')
    fresh(result,now,ref)
    return result
