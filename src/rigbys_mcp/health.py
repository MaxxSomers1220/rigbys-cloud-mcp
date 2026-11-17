"""Public operational feed status; read real persisted build metadata only."""
from datetime import datetime
import anyio
from fastapi import APIRouter
from starlette.responses import JSONResponse

from rigbys_feed.database import health as feed_health
from .repository import read_connection
from . import SERVER_VERSION

router=APIRouter()
SOURCES=('grants_gov','nih_reporter','openalex')
STATUSES={'ok','refresh_failed','success','failed','never_run','unavailable','unknown','fixture'}


def timestamp(value):
    try:
        if not isinstance(value,str):return None
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        return parsed.isoformat() if parsed.tzinfo else None
    except (ValueError,TypeError):
        return None


def status_document():
    with read_connection() as conn:
        state=feed_health(conn)
    sources={}
    for name in SOURCES:
        source=(state.get('sources') or {}).get(name) or {}
        if not isinstance(source,dict):source={}
        status=source.get('status','never_run')
        item={'status':status if status in STATUSES else 'unknown'}
        for field in ('last_success_at','oldest_response_at'):
            value=timestamp(source.get(field))
            if value is not None:item[field]=value
        reused=source.get('reused_weekly_cache')
        if isinstance(reused,bool):item['reused_weekly_cache']=reused
        sources[name]=item
    return {'feed_generated_at':state['feed_generated_at'],
            'last_build_status':state['last_build_status'], 'last_attempt_at':state['last_attempt_at'],
            'sources':sources,'last_build_status_per_source':{name:item['status'] for name,item in sources.items()},
            'server_version':SERVER_VERSION}


@router.get('/health')
async def health_endpoint():
    try:
        result=await anyio.to_thread.run_sync(status_document)
        return JSONResponse(result,headers={'Cache-Control':'no-store'})
    except Exception:
        return JSONResponse({'feed_generated_at':None,'last_build_status':'unavailable',
            'sources':{name:{'status':'unavailable'} for name in SOURCES},
            'last_build_status_per_source':{name:'unavailable' for name in SOURCES},
            'server_version':SERVER_VERSION,'error':'Health status is temporarily unavailable.'},
            status_code=503,headers={'Cache-Control':'no-store'})
