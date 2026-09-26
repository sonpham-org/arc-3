import { actionLabel, projectTree } from "./harness-tree.js?v=20260926-reasoning1";
import { renderDecision } from "./decision.js?v=20260926-harness";
(() => {
  const $ = id => document.getElementById(id);
  const state = {game:null, tree:null, node:null, nodes:new Map(), preset:null, busy:false, generation:0, run:null, runSequence:0, runner:null};
  let nodeRequest=0, latestRunNode=null, liveTranscript="", liveTruncated=false;
  const traceCache=new Map();
  let selectedReasoning=null;
  async function hydrateNodes(items,tree,generation){
    for(let i=0;i<items.length;i+=4){
      const records=await Promise.all(items.slice(i,i+4).map(n=>traceCache.get(n.id)||api('/trees/'+tree+'/nodes/'+n.id)));
      if(tree!==state.tree||generation!==state.generation)return false;
      for(const n of records){traceCache.set(n.id,n);if(traceCache.size>256)traceCache.delete(traceCache.keys().next().value);state.nodes.set(n.id,{...state.nodes.get(n.id),...n});}
    }
    return true;
  }
  async function inspectReasoning(reason){
    $('followTrace').checked=false;showRail();
    await selectNode(reason.resumeId);
    const request=nodeRequest,tree=state.tree,generation=state.generation;
    selectedReasoning=reason.id;drawTree();renderTraceNavigation();
    $('nodeTitle').textContent='Reasoning turn';$('nodeKind').textContent='Reasoning turn';
    $('nodeNote').textContent='Branching here starts alternative reasoning from this turn’s input state. Edit prompts/settings, then start a new run.';
    $('traceReview').replaceChildren(element('p','Loading this reasoning turn…','empty'));
    const page=await api('/runs/'+reason.runId+'/nodes?after='+Math.max(0,reason.sequence-1));
    if(request!==nodeRequest||tree!==state.tree)return;
    const end=page.items.findIndex(n=>n.kind==='turn-boundary');
    const turn=page.items.slice(0,end<0?undefined:end+1);
    if(!await hydrateNodes(turn,tree,generation)||request!==nodeRequest)return;
    const input=state.node,raw=turn.map(n=>traceCache.get(n.id)?.transcript||'').join('');
    renderTrace({...input,id:reason.id,displayTitle:'Reasoning turn',transcript:raw.slice(-300000)});
    $('traceScope').textContent='Reasoning from action state '+input.legalActionCount+' · '+(end<0?'saved portion; turn may continue':'through the completed turn')+(raw.length>300000?' · latest 300,000 characters':'');
    drawTree();
  }

  function showRail(trace=true){$('tracePanel').hidden=!trace;$('promptsPanel').hidden=trace;$('traceTab').setAttribute('aria-pressed',String(trace));$('promptRailTab').setAttribute('aria-pressed',String(!trace));}
  function resetTrace(){++nodeRequest;selectedReasoning=null;latestRunNode=null;liveTranscript='';liveTruncated=false;traceCache.clear();$('traceReview').replaceChildren(element('p','Select a saved node or start a run.','empty'));$('traceScope').textContent='Trace updates when actions and turn boundaries are saved.';$('traceRunStatus').textContent='No active run';renderTraceNavigation();}
  function renderTraceNavigation(){
    const nodes=projectTree([...state.nodes.values()]);$('traceNodeSelect').replaceChildren(...nodes.map(n=>new Option((n.id==='root'?'Root':n.kind==='reasoning'?'Reasoning turn from action '+n.legalActionCount:actionLabel(n)+' · action '+n.legalActionCount)+(n.createdAt?' · '+new Date(n.createdAt).toLocaleTimeString():''),n.id)));
    $('traceNodeSelect').value=selectedReasoning||state.node?.id||'';const i=nodes.findIndex(n=>n.id===(selectedReasoning||state.node?.id));$('tracePrevious').disabled=i<=0;$('traceNext').disabled=i<0||i===nodes.length-1;
  }
  function renderTrace(node){
    const live=$('followTrace').checked&&node.id===latestRunNode;
    const raw=live?liveTranscript:(node.transcript||''),sections=[];
    const markers=[...raw.matchAll(/^\[(SYSTEM PROMPT|USER PROMPT|THINKING|ASSISTANT|OUTPUT|ACTION_RESPONSE|ANALYZER STATUS|MODEL CONTEXT|MODEL RESPONSE META|PROMPT LOG SNAPSHOT|TOOL CALL:[^\]\r\n]*|TOOL RESULT:[^\]\r\n]*|ERROR[^\]\r\n]*)\][ \t]*\r?$/gm)];
    if(markers.length){if(markers[0].index>0)sections.push({label:'CONTINUED TRANSCRIPT',content:raw.slice(0,markers[0].index)});markers.forEach((m,i)=>sections.push({label:m[1],content:raw.slice(m.index+m[0].length,markers[i+1]?.index??raw.length).replace(/^\r?\n/,'')}));}
    else if(raw)sections.push({label:'TRANSCRIPT',content:raw});
    $('traceScope').textContent=live?('Following this run · '+(liveTruncated?'latest 300,000 characters · ':'')+'updates at saved actions and turn boundaries.'):('Selected node · transcript since its previous saved node.');
    if(!raw){$('traceReview').replaceChildren(element('p',node.id==='root'?'Root has no model trace yet.':'No new transcript text was saved at this node. Use the arrows to inspect neighboring saved nodes.','empty'));return;}
    const panel=$('traceReview'),atEnd=panel.scrollHeight-panel.scrollTop-panel.clientHeight<60,scroll=panel.scrollTop;
    const expanded=[...panel.querySelectorAll('details')].map(d=>d.open);
    renderDecision(panel,{metaText:node.levelsCompleted+' levels completed',title:node.displayTitle||('Action '+node.legalActionCount+' · '+(node.kind==='turn-boundary'?'completed turn checkpoint':actionLabel(node))),score:node.levelsCompleted,level:node.levelsCompleted+1,toolCallCount:sections.filter(s=>s.label.startsWith('TOOL CALL')).length,localContext:{sections}},{showFrames:false});
    if(live){panel.querySelectorAll('details').forEach((d,i)=>{if(i<expanded.length)d.open=expanded[i];});panel.scrollTop=atEnd?panel.scrollHeight:scroll;}else panel.scrollTop=0;
  }
  async function inspectNode(id){if(id.startsWith('reasoning:')){const reason=projectTree([...state.nodes.values()]).find(n=>n.id===id);if(reason)return inspectReasoning(reason);return;}$('followTrace').checked=false;showRail();await selectNode(id);}
  const palette=['#ffffff','#cccccc','#999999','#666666','#333333','#000000','#e53aa3','#ff7bcc','#f93c31','#1e93ff','#88d8f1','#ffdc00','#ff851b','#921231','#4fcc30','#a356d6'];
  const notice = message => { $('toast').textContent=message; $('toast').classList.add('show'); setTimeout(()=>$('toast').classList.remove('show'),6000); };
  async function api(path,body) {
    const response=await fetch('/api/v1/harness'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
    if(response.redirected||response.status===401){location.assign('/oauth2/start?rd='+encodeURIComponent(location.pathname));throw new Error('Please sign in');}
    const data=await response.json().catch(()=>({detail:'The backend is unavailable'}));
    if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
    return data;
  }
  function element(tag, text, className) { const e=document.createElement(tag); if(text!==undefined)e.textContent=text;if(className)e.className=className;return e; }
  function drawGrid(canvas, frame) {
    if(!frame?.grid?.length)return;
    canvas.width=frame.grid[0].length;canvas.height=frame.grid.length;
    const ctx=canvas.getContext('2d');frame.grid.forEach((row,y)=>row.forEach((color,x)=>{ctx.fillStyle=palette[color]||'#555';ctx.fillRect(x,y,1,1)}));
  }
  async function startRun(){
    if(!state.game||state.busy)return;state.busy=true;
    try{
      const config=settings();
      if(!state.tree){const tree=await api('/trees',{game_id:state.game.id,settings:config,request_id:crypto.randomUUID()});state.tree=tree.id;$('treeSelect').add(new Option('Current tree · '+tree.id.slice(0,6),tree.id));$('treeSelect').value=tree.id;await selectNode('root');}
      const result=await api('/trees/'+state.tree+'/runs',{parent_id:state.node.id,settings:config,request_id:crypto.randomUUID()});
      state.run=result.id;state.runSequence=0;latestRunNode=null;liveTranscript='';liveTruncated=false;$('followTrace').checked=true;showRail();$('traceRunStatus').textContent='Queued · waiting for saved trace';$('startRun').textContent='Cancel run';notice(result.message||'Run queued. The RTX VM wakes if it is stopped.');pollRun();
    }catch(error){notice(error.message)}finally{state.busy=false}
  }
  async function pollRun(){
    if(!state.run)return;
    const runId=state.run,treeId=state.tree;
    try{
      const [run,page]=await Promise.all([api('/runs/'+runId),api('/runs/'+runId+'/nodes?after='+state.runSequence)]);
      if(runId!==state.run||treeId!==state.tree)return;
      // Fetch only newly committed artifacts with bounded request concurrency.
      const newRecords=[];
      for(let i=0;i<page.items.length;i+=4){
        const records=await Promise.all(page.items.slice(i,i+4).map(n=>api('/trees/'+treeId+'/nodes/'+n.id)));
        if(runId!==state.run||treeId!==state.tree)return;
        newRecords.push(...records);
      }
      for(const node of newRecords){traceCache.set(node.id,node);if(traceCache.size>256)traceCache.delete(traceCache.keys().next().value);liveTranscript+=node.transcript||'';if(liveTranscript.length>300000){liveTranscript=liveTranscript.slice(-300000);liveTruncated=true;}}
      for(const node of page.items){state.nodes.set(node.id,{...node,action:traceCache.get(node.id)?.action});state.runSequence=Math.max(state.runSequence,node.sequence);}
      drawTree();$('gameTreeState').textContent='Run '+run.status;
      $('traceRunStatus').textContent=run.status;renderTraceNavigation();
      if(page.items.length){latestRunNode=page.items.at(-1).id;if($('followTrace').checked)await selectNode(latestRunNode);}
      if(['failed','cancelled','completed'].includes(run.status)&&page.items.length<100){state.run=null;$('startRun').textContent='＋ New run';if(run.error)notice(run.error);return;}
    }catch(error){notice(error.message)}
    setTimeout(pollRun,2000);
  }
  const settingsGroups={
    'Tree core':['compaction','context_window'],
    'Actions & budget':['action_cap','action_cap_mode','game_seconds','budget_reminder'],
    'Model sampling':['temperature','top_p','top_k','thinking','seed','max_output_tokens'],
    'Python tools':['tool_output_tokens','tool_timeout_seconds','tool_steps','yield_seconds'],
    'Animation & observations':['animation_checkpoint','animation_checkpoint_max_per_level','animation_checkpoint_cooldown','animation_storyboard_tokens','multimodal_context','multimodal_upscale'],
    'Advanced animation':['animation_min_changed','animation_exposed_keyframes','animation_min_spatial_frames','animation_min_spatial_unique_cells','animation_min_spatial_change_sum'],
    'User prompt behavior':['user_prompt_mode']
  };
  const labels={compaction:'Compaction mechanism',context_window:'Maximum context tokens',action_cap:'Actions per clean return',max_output_tokens:'Maximum output tokens (0 = dynamic)',tool_steps:'Tool steps (0 = unlimited)',game_seconds:'Run time budget (seconds)',top_k:'Top K (−1 = disabled)'};
  function renderSettings(preset) {
    $('agentPanel').replaceChildren();
    const model=element('p',preset.model.id,'hint');$('agentPanel').append(model);
    for(const [group,keys] of Object.entries(settingsGroups)) {
      const details=element('details');details.open=true;details.append(element('summary',group));const fields=element('div',undefined,'group-body');details.append(fields);
      for(const key of keys) {
        const spec=preset.schema.properties[key],row=element('div',undefined,'field field-inline'),label=element('label',labels[key]||key.replaceAll('_',' '));label.htmlFor='setting-'+key;
        let input;
        if(spec.enum){input=element('select');spec.enum.forEach(value=>input.add(new Option(value.replaceAll('_',' '),value)));}
        else{input=element('input');input.type=spec.type==='boolean'?'checkbox':'number';input.step=spec.type==='number'?'any':'1';if(spec.minimum!==undefined)input.min=spec.minimum;if(spec.maximum!==undefined)input.max=spec.maximum;}
        input.id='setting-'+key;input.dataset.setting=key;row.append(label,input);fields.append(row);
      }
      $('agentPanel').append(details);
    }
    const hint=element('p','The clean-return cap limits one action batch. Compaction v5 writes a game notebook at the half-context swap.','hint');$('agentPanel').append(hint);
    fillSettings(preset.settings);
  }
  function fillSettings(settings) {
    for(const [key,value] of Object.entries(settings)) {
      const input=$('setting-'+key);if(input){if(input.type==='checkbox')input.checked=value;else input.value=value;}
    }
    $('systemPrompt').value=settings.system_prompt;$('userPrompt').value=settings.user_prompt;$('compactionPrompt').value=settings.compaction_prompt;
    for(const key of ['compaction','context_window'])$('setting-'+key).disabled=!!state.tree;
    const base=document.querySelector('.config-base');base.querySelector('strong').textContent=state.tree?'Committed tree · Compaction base':'Root · Compaction defaults';base.querySelector('small').textContent=state.tree?'Compaction and context locked; branch settings editable':'Editable until the first action commits this tree';base.querySelector('.chip').textContent=state.tree?'core locked':'uncommitted';
    $('systemCount').textContent=settings.system_prompt.length+' chars';$('userCount').textContent=settings.user_prompt.length+' chars';
  }
  function settings() {
    const result={...state.preset.settings};
    document.querySelectorAll('[data-setting]').forEach(input=>{
      if(!input.checkValidity())throw new Error('Please correct '+input.dataset.setting.replaceAll('_',' '));
      result[input.dataset.setting]=input.type==='checkbox'?input.checked:input.type==='number'?Number(input.value):input.value;
    });
    return {...result,system_prompt:$('systemPrompt').value,user_prompt:$('userPrompt').value,compaction_prompt:$('compactionPrompt').value};
  }
  async function selectGame(game) {
    if(state.busy)return;
    const generation=++state.generation;state.game=game;state.tree=null;state.node=null;state.nodes.clear();resetTrace();
    state.run=null;state.runSequence=0;$('startRun').textContent='＋ New run';$('startRun').disabled=!state.runner?.provisioned;
    document.querySelectorAll('.game-tile').forEach(tile=>tile.setAttribute('aria-pressed',String(tile.dataset.gameId===game.id)));
    $('traceHeading').textContent=game.title;$('treeHeading').textContent='Run tree · '+game.title;
    fillSettings(state.preset.settings);$('treeSelect').disabled=true;$('gameTreeState').textContent='Loading trees…';
    drawTree();renderActions(null);
    try {
      const [frame,trees]=await Promise.all([api('/games/'+game.id+'/preview'),api('/trees?game_id='+encodeURIComponent(game.id))]);
      if(generation!==state.generation)return;
      drawGrid($('gameCanvas'),frame);$('treeSelect').replaceChildren(new Option('New tree · Compaction root',''));
      trees.items.forEach(tree=>$('treeSelect').add(new Option(new Date(tree.createdAt).toLocaleString()+' · '+tree.id.slice(0,6),tree.id)));
      $('treeSelect').disabled=false;$('gameTreeState').textContent=trees.items.length+' saved trees';
      renderActions(frame);$('nodeTitle').textContent='Blank root · '+game.title;$('nodeStatus').textContent='Preview · no saved actions';
      $('nodeNote').textContent='Your first human action creates a tree and locks its compaction mechanism and context window.';
    } catch(error){notice(error.message);$('gameTreeState').textContent='Could not load trees';}
  }
  async function selectTree(treeId) {
    if(state.busy)return;
    if(!treeId)return selectGame(state.game);
    ++state.generation;state.run=null;state.runSequence=0;$('startRun').textContent='＋ New run';state.tree=treeId;state.node=null;state.nodes.clear();resetTrace();await selectNode('root');await expandNode('root');
  }
  async function selectNode(id) {
    const tree=state.tree,generation=state.generation,request=++nodeRequest;
    const node=traceCache.get(id)||await api('/trees/'+tree+'/nodes/'+id);
    if(tree!==state.tree||generation!==state.generation||request!==nodeRequest)return;
    selectedReasoning=null;state.node=node;state.nodes.set(id,node);drawGrid($('gameCanvas'),node.frame);fillSettings(node.settings);renderActions(node.frame);drawTree();
    $('nodeTitle').textContent=id==='root'?'Root · '+state.game.title:actionLabel(node)+' · action '+node.legalActionCount;
    $('nodeStatus').textContent=node.state+' · level '+(node.levelsCompleted+1);$('nodeKind').textContent=node.kind==='turn-boundary'?'Completed turn checkpoint':'Action';
    $('nodeLegal').textContent=node.legalActionCount;$('nodeNote').textContent='This saved state can start another branch. Compaction and context remain fixed.';
    $('branchFromNode').disabled=false;$('branchFromNode').textContent='New reasoning branch';
    renderTraceNavigation();renderTrace(node);
    $('loadChildren').disabled=false;
  }
  async function expandNode(id) {
    const tree=state.tree,generation=state.generation,parent=state.nodes.get(id),after=parent?.nextChildren||'';
    const page=await api('/trees/'+tree+'/nodes?parent_id='+id+'&after='+after);
    if(tree!==state.tree||generation!==state.generation)return;
    page.items.forEach(node=>state.nodes.set(node.id,{...state.nodes.get(node.id),...node}));await hydrateNodes(page.items,tree,generation);if(tree!==state.tree||generation!==state.generation)return;if(parent)parent.nextChildren=page.next;
    $('nodeChildren').textContent=page.items.length+(page.next?' + more':'')+' children';
    $('childNodes').replaceChildren();for(const node of page.items){const button=element('button',node.kind==='turn-boundary'?'Completed turn · after action '+node.legalActionCount:actionLabel(state.nodes.get(node.id))+' · action '+node.legalActionCount,'secondary');button.addEventListener('click',()=>inspectNode(node.id).then(()=>expandNode(node.id)).catch(e=>notice(e.message)));$('childNodes').append(button);}drawTree();renderTraceNavigation();
  }
  async function performAction(action,x,y) {
    if(state.busy||!state.game)return;state.busy=true;renderActions(state.frame);
    try {
      const config=settings();
      if(!state.tree){const tree=await api('/trees',{game_id:state.game.id,settings:config,request_id:crypto.randomUUID()});state.tree=tree.id;$('treeSelect').add(new Option('Current tree · '+tree.id.slice(0,6),tree.id));$('treeSelect').value=tree.id;await selectNode('root');}
      const parent=state.node.id,result=await api('/trees/'+state.tree+'/actions',{parent_id:parent,action,x,y,settings:config,request_id:crypto.randomUUID()});
      await selectNode(result.id);await expandNode(parent);
    }catch(error){notice(error.message)}finally{state.busy=false;renderActions(state.node?.frame||state.frame);}
  }
  function renderActions(frame) {
    state.frame=frame;
    const box=$('gameActions');box.replaceChildren();
    const names={0:'Reset',1:'↑',2:'↓',3:'←',4:'→',5:'Action 5',6:'Click grid',7:'Action 7'};
    for(const action of [0,...new Set(frame?.availableActions||[])]) {
      const button=element('button',names[action],'secondary');button.disabled=state.busy||!frame||action===6;
      button.addEventListener('click',()=>performAction(action));box.append(button);
    }
    $('frameStatus').textContent=frame?frame.state+' · '+frame.levelsCompleted+'/'+frame.winLevels+' levels':'Choose a game';
  }
  let hitNodes=[];
  function treePositions(nodes) {
    const byId=new Map(nodes.map(n=>[n.id,n])),children=new Map(),positions=new Map();
    const order=(a,b)=>String(a.createdAt||'').localeCompare(String(b.createdAt||''))||a.id.localeCompare(b.id);
    for(const node of nodes){const list=children.get(node.parentId)||[];list.push(node);children.set(node.parentId,list);}
    for(const list of children.values())list.sort(order);
    let lastLane=-1;
    const roots=nodes.filter(n=>!byId.has(n.parentId)).sort(order),stack=roots.slice().reverse().map(node=>({node,lane:null}));
    while(stack.length){const {node,lane}=stack.pop();if(positions.has(node.id))continue;
      const actualLane=lane??++lastLane,isGate=node.id!=='root'&&node.kind==='reasoning';
      positions.set(node.id,{x:42+node.legalActionCount*110+(isGate?55:0),y:62+actualLane*84});
      const descendants=children.get(node.id)||[];
      for(let i=descendants.length-1;i>=0;i--)stack.push({node:descendants[i],lane:i===0?actualLane:null});
    }
    return {positions,lanes:lastLane+1};
  }
  function drawTree() {
    const viewport=$('treeViewport'),canvas=$('treeCanvas'),nodes=projectTree([...state.nodes.values()]);
    const {positions,lanes}=treePositions(nodes);
    const width=Math.max(viewport.clientWidth,100+nodes.reduce((m,n)=>Math.max(m,n.legalActionCount),0)*110+55),height=Math.max(240,lanes*84+80);
    $('treeExtent').style.width=width+'px';$('treeExtent').style.height=height+'px';
    const dpr=devicePixelRatio||1;canvas.width=viewport.clientWidth*dpr;canvas.height=viewport.clientHeight*dpr;canvas.style.width=viewport.clientWidth+'px';canvas.style.height=viewport.clientHeight+'px';
    canvas.style.transform=`translate(${viewport.scrollLeft}px,${viewport.scrollTop}px)`;
    const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.translate(-viewport.scrollLeft,-viewport.scrollTop);ctx.font='10px system-ui';hitNodes=[];
    ctx.strokeStyle='#e5e7eb';ctx.fillStyle='#6b7280';
    for(let action=Math.max(0,Math.floor((viewport.scrollLeft-42)/110));42+action*110<viewport.scrollLeft+viewport.clientWidth;action++){
      const x=42+action*110;ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,height);ctx.stroke();ctx.fillText(String(action),x-3,20+viewport.scrollTop);
    }
    if(!nodes.length){ctx.fillStyle='#64748b';ctx.fillText('Root · 0 actions · choose your settings, then play',28,90);}
    // Edges and hit targets share coordinates, including reasoning nodes.
    ctx.strokeStyle='#8b9db8';ctx.lineWidth=1.5;
    for(const node of nodes){const point=positions.get(node.id),parent=positions.get(node.parentId);if(!parent)continue;
      if(Math.max(point.x,parent.x)<viewport.scrollLeft||Math.min(point.x,parent.x)>viewport.scrollLeft+viewport.clientWidth||Math.max(point.y,parent.y)<viewport.scrollTop||Math.min(point.y,parent.y)>viewport.scrollTop+viewport.clientHeight)continue;
      ctx.beginPath();ctx.moveTo(parent.x,parent.y);
      if(parent.x===point.x)ctx.lineTo(point.x,point.y);else{const mid=(parent.x+point.x)/2;ctx.bezierCurveTo(mid,parent.y,mid,point.y,point.x,point.y);}ctx.stroke();
    }
    for(const node of nodes){const {x,y}=positions.get(node.id);if(x<viewport.scrollLeft-30||x>viewport.scrollLeft+viewport.clientWidth+30||y<viewport.scrollTop-30||y>viewport.scrollTop+viewport.clientHeight+30)continue;
      const selected=selectedReasoning?node.id===selectedReasoning:node.id===state.node?.id,gate=node.kind==='reasoning';
      ctx.fillStyle=selected?'#2563eb':gate?'#fff2d8':'#e7f0ff';ctx.strokeStyle=gate?'#ad762f':'#6389c3';ctx.beginPath();
      if(gate){ctx.moveTo(x,y-8);ctx.lineTo(x+8,y);ctx.lineTo(x,y+8);ctx.lineTo(x-8,y);ctx.closePath();}else ctx.roundRect(x-20,y-13,40,26,6);
      ctx.fill();ctx.stroke();ctx.fillStyle=selected?'#fff':'#24456b';ctx.textAlign='center';
      if(!gate)ctx.fillText(actionLabel(node),x,y+3);
      ctx.fillStyle='#526277';ctx.fillText(node.id==='root'?'Root':gate?'Reasoning turn':(node.action?.id===6?'Click '+node.action.data?.x+','+node.action.data?.y:''),x,y+(gate?20:-16));ctx.textAlign='left';hitNodes.push({x,y,id:node.id,node});
    }
    $('runCount').textContent=nodes.length+' loaded nodes';
  }
  async function init() {
    const [preset,catalog]=await Promise.all([api('/preset'),api('/games')]);state.preset=preset;renderSettings(preset);
    const tiles=document.querySelector('.game-tiles')||document.querySelector('.game-tile').parentElement;tiles.replaceChildren();
    for(const game of catalog){const button=element('button',undefined,'game-tile');button.type='button';button.dataset.gameId=game.id;button.setAttribute('aria-pressed','false');const canvas=element('canvas');canvas.style.imageRendering='pixelated';canvas.style.width='100%';canvas.style.height='72px';canvas.style.objectFit='contain';button.append(canvas,element('strong',game.title),element('small',game.official?'ARC3 Foundation':'Community'));button.addEventListener('click',()=>selectGame(game));tiles.append(button);
      const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){observer.disconnect();api('/games/'+game.id+'/preview').then(frame=>drawGrid(canvas,frame)).catch(()=>{});}});observer.observe(button);
    }
    $('gamePickerHeading').textContent='Choose a game · '+catalog.length+' games · Foundation first';
    await refreshRunner();
  }
  async function refreshRunner(){const runner=await api('/runner');state.runner=runner;const gpu=runner.provisioningModel==='SPOT'?'Spot RTX':'RTX';document.querySelector('.runner-state').textContent=runner.status==='quota-pending'?gpu+' · awaiting GPU quota':runner.status==='not-provisioned'?gpu+' · provisioning pending':gpu+' · '+runner.status;document.querySelector('.runner-state').title=runner.reason||'Three run slots; shutdown after 30 idle minutes';$('startRun').title=runner.provisioned?'Run with the selected settings':runner.reason||'Runner provisioning pending';$('startRun').disabled=!runner.provisioned||!state.game;setTimeout(()=>refreshRunner().catch(()=>{}),15000);}
  $('traceTab').addEventListener('click',()=>showRail());
  $('promptRailTab').addEventListener('click',()=>showRail(false));
  $('followTrace').addEventListener('change',()=>{if($('followTrace').checked&&latestRunNode)selectNode(latestRunNode).catch(e=>notice(e.message));else if(state.node)renderTrace(state.node);});
  $('traceNodeSelect').addEventListener('change',e=>inspectNode(e.target.value).catch(e=>notice(e.message)));
  for(const [id,direction] of [['tracePrevious',-1],['traceNext',1]])$(id).addEventListener('click',()=>{const nodes=projectTree([...state.nodes.values()]).map(n=>n.id),next=nodes[nodes.indexOf(selectedReasoning||state.node?.id)+direction];if(next)inspectNode(next).catch(e=>notice(e.message));});
  $('treeSelect').addEventListener('change',event=>selectTree(event.target.value).catch(e=>notice(e.message)));
  $('startRun').addEventListener('click',()=>state.run?api('/runs/'+state.run+'/cancel',{}).then(()=>notice('Cancellation requested')).catch(e=>notice(e.message)):startRun());
  $('pixelSmoothing').addEventListener('change',event=>$('gameCanvas').style.imageRendering=event.target.checked?'pixelated':'auto');
  $('canvasScale').addEventListener('change',event=>{$('gameCanvas').style.width=event.target.selectedIndex===0?'min(100%,510px)':($('gameCanvas').width*event.target.selectedIndex)+'px';});
  $('gameCanvas').addEventListener('mousemove',event=>{if(!$('gridCoordinates').checked)return;const rect=event.target.getBoundingClientRect();$('frameStatus').textContent='x '+Math.floor((event.clientX-rect.left)*event.target.width/rect.width)+' · y '+Math.floor((event.clientY-rect.top)*event.target.height/rect.height);});
  $('loadChildren').addEventListener('click',()=>expandNode(state.node.id).catch(e=>notice(e.message)));
  $('branchFromNode').addEventListener('click',()=>{if(state.run){notice('Cancel the active run before starting another branch in this tab.');return;}startRun();});
  $('gameCanvas').addEventListener('click',event=>{if(!state.frame?.availableActions.includes(6))return;const rect=event.target.getBoundingClientRect();performAction(6,Math.floor((event.clientX-rect.left)*event.target.width/rect.width),Math.floor((event.clientY-rect.top)*event.target.height/rect.height));});
  $('treeViewport').addEventListener('scroll',()=>requestAnimationFrame(drawTree));
  $('treeCanvas').addEventListener('click',event=>{const rect=event.target.getBoundingClientRect(),x=event.clientX-rect.left+$('treeViewport').scrollLeft,y=event.clientY-rect.top+$('treeViewport').scrollTop;const hit=hitNodes.find(n=>Math.abs(n.x-x)<(n.node.kind==='reasoning'?12:22)&&Math.abs(n.y-y)<15);if(hit)(hit.node.kind==='reasoning'?inspectReasoning(hit.node):inspectNode(hit.id).then(()=>expandNode(hit.id))).catch(e=>notice(e.message));});
  new ResizeObserver(()=>requestAnimationFrame(drawTree)).observe($('treeViewport'));
  const tabs=[...document.querySelectorAll('.settings-tab')];function activateTab(tab){tabs.forEach(t=>{t.setAttribute('aria-selected',String(t===tab));t.tabIndex=t===tab?0:-1;$(t.getAttribute('aria-controls')).hidden=t!==tab;});}
  tabs.forEach((tab,index)=>{tab.addEventListener('click',()=>activateTab(tab));tab.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:tabs.length-1))%tabs.length;activateTab(tabs[next]);tabs[next].focus();});});
  $('themeToggle').addEventListener('click',()=>document.body.classList.toggle('dark'));
  init().catch(error=>{notice(error.message);$('gamePickerHeading').textContent='Connection unavailable';});
})();
