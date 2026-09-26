// A display projection of immutable checkpoints; resume IDs always stay server-owned.
export function actionLabel(node) {
  const action=node.action;
  if(!action)return node.id==='root'?'Root':'…';
  const id=Number(String(action.id).replace(/^ACTION/i,''));
  const name={0:'Reset',1:'UP',2:'DOWN',3:'LEFT',4:'RIGHT',5:'A5',6:'Click',7:'A7'}[id]||String(action.id);
  return name;
}
export function projectTree(records) {
  const byId=new Map(records.map(n=>[n.id,n]));
  const checkpoint=n=>n&&n.id!=='root'&&n.kind==='turn-boundary'&&!n.action;
  function visibleParent(id){const seen=new Set();while(checkpoint(byId.get(id))&&!seen.has(id)){seen.add(id);id=byId.get(id).parentId;}return id;}
  const result=[];
  for(const node of records){
    if(checkpoint(node))continue;
    let parentId=visibleParent(node.parentId),parent=byId.get(node.parentId);
    if(node.id!=='root'&&node.runId&&node.runId!=='human'&&(checkpoint(parent)||parent?.runId!==node.runId)){
      const id='reasoning:'+node.id;
      result.push({id,parentId,kind:'reasoning',legalActionCount:parent?.legalActionCount??Math.max(0,node.legalActionCount-1),createdAt:node.createdAt,resumeId:node.parentId,firstActionId:node.id,runId:node.runId,sequence:node.sequence});
      parentId=id;
    }
    result.push({...node,parentId,kind:node.id==='root'?'root':'action'});
  }
  return result;
}
