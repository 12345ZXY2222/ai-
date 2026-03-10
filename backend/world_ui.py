import os
import requests
from typing import Any, Dict, List, Optional, Tuple

from nicegui import ui


BACKEND_BASE = os.environ.get('WORLD_UI_BACKEND', 'http://127.0.0.1:8001/api')
DEFAULT_WORLD_PRESET = 'basketball_court'


def api_headers(token: Optional[str]) -> Dict[str, str]:
    return {'Authorization': f'Bearer {token}'} if token else {}


def post_token(username: str, password: str) -> str:
    r = requests.post(
        f'{BACKEND_BASE}/token',
        data={'username': username, 'password': password},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    return data['access_token']


def get_agents(token: str) -> List[Dict[str, Any]]:
    r = requests.get(f'{BACKEND_BASE}/agents', headers=api_headers(token), timeout=20)
    r.raise_for_status()
    return r.json()


def create_agent(token: str, name: str, provider: str, model: str, persona: str) -> Dict[str, Any]:
    payload = {
        'name': name,
        'provider': provider,
        'model': model,
        'persona': persona or None,
        'long_term_memory': [],
    }
    r = requests.post(f'{BACKEND_BASE}/agents', json=payload, headers=api_headers(token), timeout=30)
    r.raise_for_status()
    return r.json()


def inject_memory(token: str, agent_id: str, content: str, importance: int) -> Dict[str, Any]:
    r = requests.post(
        f'{BACKEND_BASE}/agents/{agent_id}/memory/inject',
        json={'content': content, 'importance': int(importance)},
        headers=api_headers(token),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def list_worlds(token: str) -> List[Dict[str, Any]]:
    r = requests.get(f'{BACKEND_BASE}/worlds', headers=api_headers(token), timeout=20)
    r.raise_for_status()
    return r.json()


def create_world(token: str, name: str, width: int, height: int, preset: Optional[str]) -> Dict[str, Any]:
    r = requests.post(
        f'{BACKEND_BASE}/worlds',
        json={'name': name, 'width': int(width), 'height': int(height), 'preset': preset},
        headers=api_headers(token),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def get_world(token: str, world_id: str) -> Dict[str, Any]:
    r = requests.get(f'{BACKEND_BASE}/worlds/{world_id}', headers=api_headers(token), timeout=20)
    r.raise_for_status()
    return r.json()


def update_world_grid(token: str, world_id: str, grid: List[List[str]]) -> Dict[str, Any]:
    r = requests.put(
        f'{BACKEND_BASE}/worlds/{world_id}',
        json={'grid': grid},
        headers=api_headers(token),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def get_world_ascii(token: str, world_id: str) -> str:
    r = requests.get(f'{BACKEND_BASE}/worlds/{world_id}/ascii', headers=api_headers(token), timeout=20)
    r.raise_for_status()
    return r.json().get('ascii', '')


def place_agent(token: str, world_id: str, agent_id: str, x: int, y: int) -> Dict[str, Any]:
    r = requests.post(
        f'{BACKEND_BASE}/worlds/{world_id}/agents/place',
        json={'agent_id': agent_id, 'x': int(x), 'y': int(y)},
        headers=api_headers(token),
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def move_agent(token: str, world_id: str, agent_id: str, to_x: int, to_y: int) -> Dict[str, Any]:
    r = requests.post(
        f'{BACKEND_BASE}/worlds/{world_id}/agents/move',
        json={'agent_id': agent_id, 'to_x': int(to_x), 'to_y': int(to_y)},
        headers=api_headers(token),
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def plan_path(token: str, world_id: str, agent_id: str, target_x: int, target_y: int) -> List[Dict[str, int]]:
    r = requests.post(
        f'{BACKEND_BASE}/worlds/{world_id}/plan_path',
        json={'agent_id': agent_id, 'target_x': int(target_x), 'target_y': int(target_y)},
        headers=api_headers(token),
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get('path', [])


def run_dialogue_step(
    token: str,
    initiator_agent_id: str,
    partner_agent_id: Optional[str],
    prompt_template: str,
    max_turns: int,
    end_marker: str,
    world_state: Dict[str, Any],
) -> Dict[str, Any]:
    step = {
        'id': 'dialogue-1',
        'type': 'dialogue',
        'agent_ids': [initiator_agent_id],
        'prompt_template': prompt_template,
        'dialogue_max_turns': int(max_turns),
        'dialogue_auto_partner': partner_agent_id is None,
        'dialogue_partner_id': partner_agent_id,
        'dialogue_end_marker': end_marker,
        'output_var': 'dialogue_transcript',
    }
    payload = {
        'steps': [step],
        'current_step_index': 0,
        'history': [],
        'world_state': world_state,
    }
    r = requests.post(
        f'{BACKEND_BASE}/simulation/run_step',
        json=payload,
        headers=api_headers(token),
        timeout=180,
    )
    r.raise_for_status()
    return r.json()


def cell_label(cell: str) -> str:
    if cell == 'wall':
        return '#'
    if cell == 'court':
        return '.'
    return ' '


class AppState:
    token: Optional[str] = None
    username: str = ''

    agents: List[Dict[str, Any]] = []
    worlds: List[Dict[str, Any]] = []

    selected_world_id: Optional[str] = None
    selected_agent_id: Optional[str] = None

    brush: str = 'wall'  # wall|court|empty
    mode: str = 'paint'  # paint|place_agent|set_target
    target: Optional[Tuple[int, int]] = None
    last_path: List[Tuple[int, int]] = []

    world: Optional[Dict[str, Any]] = None


state = AppState()


def refresh_agents():
    if not state.token:
        return
    state.agents = get_agents(state.token)


def refresh_worlds():
    if not state.token:
        return
    state.worlds = list_worlds(state.token)


def load_world(world_id: str):
    state.selected_world_id = world_id
    state.world = get_world(state.token, world_id)
    state.last_path = []
    state.target = None


def agent_name(agent_id: str) -> str:
    for a in state.agents:
        if a.get('id') == agent_id:
            return a.get('name') or agent_id
    return agent_id


def render_grid(container: ui.element):
    container.clear()
    if not state.world:
        return

    grid = state.world.get('grid') or []
    placements = {(p.get('x'), p.get('y')): p.get('agent_id') for p in (state.world.get('agent_placements') or [])}
    path_set = set(state.last_path)
    target = state.target

    with container:
        with ui.column().classes('gap-1'):
            ui.label(f"World: {state.world.get('name')} ({state.world.get('width')}x{state.world.get('height')})")
            for y, row in enumerate(grid):
                with ui.row().classes('gap-1'):
                    for x, cell in enumerate(row):
                        label = cell_label(cell)
                        if (x, y) in placements:
                            label = 'A'
                        if target == (x, y):
                            label = 'T'
                        if (x, y) in path_set and (x, y) != target:
                            label = '*'

                        def _make_on_click(cx: int, cy: int):
                            def _on_click():
                                if not state.world:
                                    return
                                if state.mode == 'paint':
                                    new_grid = [list(r) for r in (state.world.get('grid') or [])]
                                    new_grid[cy][cx] = state.brush
                                    state.world = update_world_grid(state.token, state.world['id'], new_grid)
                                elif state.mode == 'place_agent':
                                    if not state.selected_agent_id:
                                        ui.notify('Select an agent first', type='warning')
                                        return
                                    state.world = place_agent(state.token, state.world['id'], state.selected_agent_id, cx, cy)
                                elif state.mode == 'set_target':
                                    state.target = (cx, cy)
                                render_grid(grid_container)
                            return _on_click

                        ui.button(label, on_click=_make_on_click(x, y)).props('dense flat').classes('w-7 h-7')


def ensure_logged_in():
    if not state.token:
        raise RuntimeError('Not logged in')


@ui.page('/')
def main_page():
    ui.label('Interactive World (Python-only)').classes('text-h5')

    with ui.card().classes('w-full'):
        ui.label('1) Login').classes('text-subtitle1')
        username = ui.input('Username')
        password = ui.input('Password', password=True, password_toggle_button=True)

        def do_login():
            try:
                token = post_token(username.value or '', password.value or '')
                state.token = token
                state.username = username.value or ''
                ui.notify('Login OK', type='positive')
                refresh_agents()
                refresh_worlds()
                worlds_select.options = {w['id']: w['name'] for w in state.worlds}
                agents_select.options = {a['id']: a['name'] for a in state.agents}
            except Exception as e:
                ui.notify(f'Login failed: {e}', type='negative')

        ui.button('Login', on_click=do_login)

    with ui.row().classes('w-full gap-4'):
        with ui.card().classes('w-1/3'):
            ui.label('2) Worlds').classes('text-subtitle1')

            world_name = ui.input('World name', value='Basketball Court')
            world_w = ui.number('Width', value=15, min=5, max=60)
            world_h = ui.number('Height', value=9, min=5, max=60)
            preset = ui.select(options=['', 'basketball_court'], value=DEFAULT_WORLD_PRESET, label='Preset')

            def do_create_world():
                try:
                    ensure_logged_in()
                    w = create_world(state.token, world_name.value or 'New World', int(world_w.value), int(world_h.value), preset.value or None)
                    refresh_worlds()
                    worlds_select.options = {w['id']: w['name'] for w in state.worlds}
                    worlds_select.value = w['id']
                    load_world(w['id'])
                    render_grid(grid_container)
                    ui.notify('World created', type='positive')
                except Exception as e:
                    ui.notify(f'Create world failed: {e}', type='negative')

            ui.button('Create world', on_click=do_create_world)

            worlds_select = ui.select(options={}, label='Select world')

            def on_world_change(e):
                if not e.value:
                    return
                try:
                    ensure_logged_in()
                    load_world(e.value)
                    render_grid(grid_container)
                except Exception as ex:
                    ui.notify(f'Load world failed: {ex}', type='negative')

            worlds_select.on('update:model-value', on_world_change)

            ui.separator()
            ui.label('Paint / Place').classes('text-subtitle2')
            brush = ui.select(options=['wall', 'court', 'empty'], value='wall', label='Brush')

            def on_brush(e):
                state.brush = e.value

            brush.on('update:model-value', on_brush)

            mode = ui.select(options={'paint': 'Paint cells', 'place_agent': 'Place agent', 'set_target': 'Set target'}, value='paint', label='Mode')

            def on_mode(e):
                state.mode = e.value

            mode.on('update:model-value', on_mode)

            ui.label('Legend: # wall, . court, A agent, T target, * path')

        with ui.card().classes('w-2/3'):
            ui.label('3) Grid').classes('text-subtitle1')
            grid_container = ui.element('div')

    with ui.row().classes('w-full gap-4'):
        with ui.card().classes('w-1/3'):
            ui.label('4) Agents').classes('text-subtitle1')
            agents_select = ui.select(options={}, label='Select agent')

            def on_agent_change(e):
                state.selected_agent_id = e.value

            agents_select.on('update:model-value', on_agent_change)

            ui.separator()
            ui.label('Create agent')
            new_name = ui.input('Name')
            provider = ui.select(options=['deepseek', 'zhipu', 'custom'], value='deepseek', label='Provider')
            model = ui.input('Model', value='deepseek-chat')
            persona = ui.textarea('Persona (system prompt)', value='')

            def do_create_agent():
                try:
                    ensure_logged_in()
                    a = create_agent(state.token, new_name.value or 'New Agent', provider.value, model.value or 'deepseek-chat', persona.value or '')
                    refresh_agents()
                    agents_select.options = {ag['id']: ag['name'] for ag in state.agents}
                    agents_select.value = a['id']
                    state.selected_agent_id = a['id']
                    ui.notify('Agent created', type='positive')
                except Exception as e:
                    ui.notify(f'Create agent failed: {e}', type='negative')

            ui.button('Create agent', on_click=do_create_agent)

        with ui.card().classes('w-2/3'):
            ui.label('5) Memory + Dialogue + Path').classes('text-subtitle1')

            with ui.row().classes('gap-4'):
                mem_agent = ui.select(options={}, label='Memory target agent')
                mem_importance = ui.number('Importance', value=3, min=1, max=10)

            mem_text = ui.textarea('Memory content', value='')

            def sync_mem_agents():
                mem_agent.options = {ag['id']: ag['name'] for ag in state.agents}

            def do_inject_memory():
                try:
                    ensure_logged_in()
                    if not mem_agent.value:
                        ui.notify('Select memory target agent', type='warning')
                        return
                    inject_memory(state.token, mem_agent.value, mem_text.value or '', int(mem_importance.value))
                    ui.notify('Memory injected', type='positive')
                except Exception as e:
                    ui.notify(f'Inject memory failed: {e}', type='negative')

            ui.button('Inject memory', on_click=do_inject_memory)

            ui.separator()
            ui.label('Dialogue')
            with ui.row().classes('gap-4'):
                dlg_initiator = ui.select(options={}, label='Initiator')
                dlg_partner = ui.select(options={}, label='Partner (optional)')

            dlg_max_turns = ui.number('Max turns', value=6, min=1, max=30)
            dlg_end_marker = ui.input('End marker', value='END_DIALOGUE')
            dlg_prompt = ui.textarea('Dialogue prompt template', value='Start a conversation in this world. When finished, output END_DIALOGUE.')
            dlg_output = ui.textarea('Dialogue output', value='').props('readonly').classes('w-full')

            def sync_dlg_agents():
                opts = {ag['id']: ag['name'] for ag in state.agents}
                dlg_initiator.options = opts
                dlg_partner.options = {'': '(auto)'} | opts

            def do_dialogue():
                try:
                    ensure_logged_in()
                    if not state.selected_world_id:
                        ui.notify('Select a world first', type='warning')
                        return
                    if not dlg_initiator.value:
                        ui.notify('Select initiator', type='warning')
                        return

                    ascii_map = get_world_ascii(state.token, state.selected_world_id)
                    prompt = (
                        f"World map (ascii):\n{ascii_map}\n\n"
                        f"You are an agent in this grid world. You know walls (#) and open cells. "
                        f"{dlg_prompt.value}"
                    )
                    partner = dlg_partner.value or None
                    world_state = {
                        'world_id': state.selected_world_id,
                        'world_ascii': ascii_map,
                        'world': state.world,
                    }

                    res = run_dialogue_step(
                        state.token,
                        dlg_initiator.value,
                        partner,
                        prompt,
                        int(dlg_max_turns.value),
                        dlg_end_marker.value or 'END_DIALOGUE',
                        world_state,
                    )
                    items = res.get('new_history_items') or []
                    lines = []
                    for it in items:
                        lines.append(f"{it.get('agent_name', 'agent')}: {it.get('content', '')}")
                    dlg_output.value = "\n".join(lines)
                    ui.notify('Dialogue step executed', type='positive')
                except Exception as e:
                    ui.notify(f'Dialogue failed: {e}', type='negative')

            ui.button('Run dialogue step', on_click=do_dialogue)

            ui.separator()
            ui.label('Path planning')
            with ui.row().classes('gap-4'):
                path_agent = ui.select(options={}, label='Path agent')
                target_hint = ui.label('Set target using Mode = Set target, then click a cell')

            def sync_path_agents():
                path_agent.options = {ag['id']: ag['name'] for ag in state.agents}

            def do_plan_path():
                try:
                    ensure_logged_in()
                    if not state.selected_world_id or not state.world:
                        ui.notify('Select a world first', type='warning')
                        return
                    if not path_agent.value:
                        ui.notify('Select a path agent', type='warning')
                        return
                    if not state.target:
                        ui.notify('Set a target cell first', type='warning')
                        return
                    pts = plan_path(state.token, state.selected_world_id, path_agent.value, state.target[0], state.target[1])
                    state.last_path = [(p['x'], p['y']) for p in pts]
                    render_grid(grid_container)
                    ui.notify(f'Path length: {len(state.last_path)}', type='positive')
                except Exception as e:
                    ui.notify(f'Plan path failed: {e}', type='negative')

            def do_move_to_target():
                try:
                    ensure_logged_in()
                    if not state.selected_world_id or not state.world:
                        ui.notify('Select a world first', type='warning')
                        return
                    if not path_agent.value:
                        ui.notify('Select a path agent', type='warning')
                        return
                    if not state.target:
                        ui.notify('Set a target first', type='warning')
                        return
                    state.world = move_agent(state.token, state.selected_world_id, path_agent.value, state.target[0], state.target[1])
                    render_grid(grid_container)
                    ui.notify('Agent moved', type='positive')
                except Exception as e:
                    ui.notify(f'Move failed: {e}', type='negative')

            with ui.row().classes('gap-2'):
                ui.button('Plan path', on_click=do_plan_path)
                ui.button('Move agent to target', on_click=do_move_to_target)

            def do_refresh_everything():
                try:
                    ensure_logged_in()
                    refresh_agents()
                    refresh_worlds()
                    agents_select.options = {ag['id']: ag['name'] for ag in state.agents}
                    sync_mem_agents()
                    sync_dlg_agents()
                    sync_path_agents()
                    worlds_select.options = {w['id']: w['name'] for w in state.worlds}
                    if state.selected_world_id:
                        load_world(state.selected_world_id)
                        render_grid(grid_container)
                    ui.notify('Refreshed', type='positive')
                except Exception as e:
                    ui.notify(f'Refresh failed: {e}', type='negative')

            ui.button('Refresh lists', on_click=do_refresh_everything)

            # Keep select options synced after login and after agent creation
            def _sync_all_selects():
                sync_mem_agents()
                sync_dlg_agents()
                sync_path_agents()

            ui.timer(1.0, _sync_all_selects)


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(title='Interactive World', host='0.0.0.0', port=int(os.environ.get('WORLD_UI_PORT', '8502')))
