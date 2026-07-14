"""AHVE FPS Server — fps-game-7802. Colyseus Multiplayer."""
import asyncio, json, random, uuid
from aiohttp import web

players = {}
bullets = []

async def index(request):
    return web.FileResponse('index.html')

async def ws_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    pid = str(uuid.uuid4())[:8]
    players[pid] = {
        'id': pid, 'x': random.uniform(-10, 10), 'z': random.uniform(-10, 10),
        'hp': 100, 'kills': 0, 'color': random.choice(['#e94560','#0f3460','#16213e','#533483','#f5a623'])
    }
    await ws.send_json({'type': 'init', 'player_id': pid, 'players': list(players.values())})
    
    # Notify others
    for oid, ows_list in request.app['clients'].items():
        if oid != pid:
            for ows in ows_list:
                await ows.send_json({'type': 'player_joined', 'player': players[pid]})
    
    request.app['clients'].setdefault(pid, []).append(ws)
    
    try:
        async for msg in ws:
            data = json.loads(msg.data)
            p = players.get(pid)
            if not p:
                continue
            
            if data.get('move'):
                p['x'] += data['move'].get('x', 0) * 0.3
                p['z'] += data['move'].get('z', 0) * 0.3
            
            if data.get('shoot'):
                bullet = {
                    'id': str(uuid.uuid4())[:6],
                    'x': p['x'], 'z': p['z'],
                    'dx': data['shoot']['dx'], 'dz': data['shoot']['dz'],
                    'owner': pid
                }
                bullets.append(bullet)
                # Check hit
                for oid, o in players.items():
                    if oid != pid:
                        dist = ((bullet['x'] - o['x'])**2 + (bullet['z'] - o['z'])**2)**0.5
                        if dist < 5:
                            o['hp'] -= 25
                            if o['hp'] <= 0:
                                o['hp'] = 100
                                o['x'] = random.uniform(-10, 10)
                                o['z'] = random.uniform(-10, 10)
                                p['kills'] += 1
                            await ws.send_json({'type': 'kill', 'victim': oid, 'kills': p['kills']})
                            break
            
            # Broadcast state
            state = {'type': 'state', 'players': list(players.values()), 'bullets': bullets[-20:]}
            for ows_list in request.app['clients'].values():
                for ows in ows_list:
                    await ows.send_json(state)
    finally:
        request.app['clients'].get(pid, []).remove(ws)
        players.pop(pid, None)
        for ows_list in request.app['clients'].values():
            for ows in ows_list:
                await ows.send_json({'type': 'player_left', 'player_id': pid})
    
    return ws

app = web.Application()
app['clients'] = {}
app.router.add_get('/', index)
app.router.add_get('/ws', ws_handler)

if __name__ == '__main__':
    web.run_app(app, port=5000)
