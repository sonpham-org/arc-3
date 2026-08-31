"""q475 Alloy Dependency -- reuse a frame-relative catalyst across nested assemblies."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,LANE,STOCK,CATALYST,PART,FRAME,LAUNCH,BAD=13,1,8,6,2,11,9,4,15
def make_plan(need,bands):return (4,2,4,4)*bands+(1,2,3)*need+(5,)
LEVELS=[
 {"name":"Catalyzed Part","need":1,"bands":1},{"name":"Shared Catalyst","need":2,"bands":1},
 {"name":"Double Field","need":2,"bands":2},{"name":"Three Assemblies","need":3,"bands":2},
 {"name":"Stable Lower Pattern","need":3,"bands":3},{"name":"Alloy Dependency","need":4,"bands":3}]
for x in LEVELS:x["plan"]=make_plan(x["need"],x["bands"])
def advance(s,a,x):
 stock,parts,origin,rotation,launched=s;stock=list(stock)
 if launched is not None:return None
 if a==1:stock[rotation]+=1
 elif a==2:stock[(rotation+1)%3]+=1
 elif a==3:
  if rotation!=0 or stock[0]<1 or stock[1]<1 or stock[2]<x["bands"]:return None
  stock[0]-=1;stock[1]-=1;parts+=1
 elif a==4:origin=(origin+1)%6;rotation=(rotation+1)%3
 elif a==5:
  if parts!=x["need"]:return None
  launched=(tuple(stock),parts,origin,rotation)
 return tuple(stock),parts,origin,rotation,launched
def target(x):
 s=((0,0,0),0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FOUNDRY
  for screen in range(3):
   x=8+screen*17;physical=(g.rotation+screen)%3;f[8:35,x:x+13]=LANE+screen%2;f[31-g.stock[physical]*4:33,x+2:x+11]=CATALYST if physical==2 else STOCK+physical
  f[40:44,8:8+g.parts*10]=PART;f[47:50,8:8+g.origin*8]=FRAME;f[53:56,8:8+g.rotation*13]=CATALYST
  if g.launched:f[38:58,56:59]=LAUNCH
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q475(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q475",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.stock=(0,0,0);self.parts=self.origin=self.rotation=0;self.launched=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.stock,self.parts,self.origin,self.rotation,self.launched),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.stock,self.parts,self.origin,self.rotation,self.launched=s
  elif a==6:
   if (self.stock,self.parts,self.origin,self.rotation,self.launched)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
