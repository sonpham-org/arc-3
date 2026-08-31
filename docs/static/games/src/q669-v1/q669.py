"""q669 Reedbed Analogy -- transfer a relation through function-changing bridges."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,SOURCE,TARGET,RELATION,BRIDGE,LINK,TRANSFER,BAD=5,10,9,12,14,11,6,13,15
LEVELS=[
 {"name":"First Bridge","ops":(1,),"bridges":1},{"name":"Reflected Bridge","ops":(1,2),"bridges":1},
 {"name":"Two Bridges","ops":(1,1,2),"bridges":2},{"name":"Rewired Analogy","ops":(2,1,1,2),"bridges":2},
 {"name":"Surface Change","ops":(1,2,1,1,2),"bridges":3},{"name":"Reedbed Analogy","ops":(2,1,2,1,1,2),"bridges":4}]
def advance(s,a,x):
 relation,source,target_links,bridges,transferred=s
 if a==1:relation=(relation+1)%4;source=((source<<1)|(source>>3))&15
 elif a==2:relation=(-relation)%4;source^=1<<(relation%4)
 elif a==3:target_links^=1<<(relation%4);bridges+=1
 elif a in (4,5):
  choice=a-4;correct=(relation+source.bit_count()+bridges)%2
  if bridges<x["bridges"] or choice!=correct:return None
  transferred=(choice,target_links)
 return relation,source,target_links,bridges,transferred
for x in LEVELS:
 base=x["ops"]+(3,)*x["bridges"];s=(0,1,0,0,None)
 for a in base:s=advance(s,a,x);assert s is not None
 x["plan"]=base+(4+((s[0]+s[1].bit_count()+s[3])%2),)
def target(x):
 s=(0,1,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER;f[8:34,8:29]=SOURCE;f[8:34,35:56]=TARGET
  for i in range(4):
   if g.source&(1<<i):f[11+i*5:14+i*5,11:26]=RELATION
   if g.target_links&(1<<i):f[11+i*5:14+i*5,38:53]=LINK
  f[40:44,8:8+g.bridges*9]=BRIDGE;f[49:53,8:8+g.relation*10]=RELATION
  if g.transferred:f[55:60,39:56]=TRANSFER
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q669(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q669",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.relation=0;self.source=1;self.target_links=self.bridges=0;self.transferred=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.relation,self.source,self.target_links,self.bridges,self.transferred),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.relation,self.source,self.target_links,self.bridges,self.transferred=s
  elif a==6:
   if (self.relation,self.source,self.target_links,self.bridges,self.transferred)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
