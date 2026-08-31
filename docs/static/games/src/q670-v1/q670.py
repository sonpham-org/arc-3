"""q670 Vault Analogy -- transfer a relation while both source and target ledgers stay conserved."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,SOURCE,TARGET,A_ECHO,B_ECHO,RELATION,TRANSFER,BAD=5,11,9,14,12,6,10,13,15
LEVELS=[
 {"name":"First Relation","ops":(1,),"apply":1},{"name":"Reflected Relation","ops":(1,2),"apply":1},
 {"name":"Two Applications","ops":(1,1,2),"apply":2},{"name":"Dual Analogy","ops":(2,1,1,2),"apply":2},
 {"name":"Surface Change","ops":(1,2,1,1,2),"apply":3},{"name":"Vault Analogy","ops":(2,1,2,1,1,2),"apply":4}]
def advance(s,a,x):
 source,target_boxes,memory,applied,transferred=s;src=[list(v) for v in source];tar=[list(v) for v in target_boxes]
 if a in (1,2):
  q=a-1;vals=[v[q] for v in src];vals=vals[-1:]+vals[:-1]
  for i,v in enumerate(vals):src[i][q]=v
 elif a==3:memory=(src[0][0]+2*src[1][1])%3
 elif a==4:
  if memory is None:return None
  q=memory%2;vals=[v[q] for v in tar];vals=vals[1:]+vals[:1]
  for i,v in enumerate(vals):tar[i][q]=v
  applied+=1
 elif a==5:
  if applied!=x["apply"]:return None
  transferred=(memory,tuple(map(tuple,tar)))
 return tuple(map(tuple,src)),tuple(map(tuple,tar)),memory,applied,transferred
for x in LEVELS:x["plan"]=x["ops"]+(3,)+(4,)*x["apply"]+(5,)
def target(x):
 s=(((2,1),(0,1),(1,0)),((1,2),(1,0),(0,1)),None,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=VAULT;f[8:34,8:29]=SOURCE;f[8:34,35:56]=TARGET
  for side,boxes in enumerate((g.source,g.target_boxes)):
   for i,(a,b) in enumerate(boxes):x=11+side*27;f[11+i*6:14+i*6,x:x+a*3]=A_ECHO;f[14+i*6:17+i*6,x:x+b*3]=B_ECHO
  f[40:44,8:28]=RELATION;f[48:52,8:8+g.applied*9]=TRANSFER
  if g.transferred:f[54:59,39:56]=TRANSFER
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q670(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q670",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.source=((2,1),(0,1),(1,0));self.target_boxes=((1,2),(1,0),(0,1));self.memory=None;self.applied=0;self.transferred=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.source,self.target_boxes,self.memory,self.applied,self.transferred),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.source,self.target_boxes,self.memory,self.applied,self.transferred=s
  elif a==6:
   if (self.source,self.target_boxes,self.memory,self.applied,self.transferred)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
