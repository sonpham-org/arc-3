"""q655 Alloy Analogy -- preserve a relation while the reference frame moves."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,LANE,SOURCE,TARGET,FRAME,TRANSFER,PROOF,BAD=8,1,11,6,2,9,4,13,15
LEVELS=[
 {"name":"Turn and Map","plan":(1,3,5)},{"name":"Reflected Map","plan":(2,3,5)},
 {"name":"Rotated Frame","plan":(4,1,3,5)},{"name":"Double Transform","plan":(1,4,4,3,5)},
 {"name":"Moving Analogy","plan":(2,4,1,4,3,5)},{"name":"Alloy Analogy","plan":(4,1,2,4,1,3,5)}]
def advance(s,a,x):
 source,target,origin,rotation,proof=s
 if a==1:source=(source+1)%4
 elif a==2:source=(-source)%4
 elif a==3:target=(source+rotation)%4
 elif a==4:origin=(origin+1)%6;rotation=(rotation+1)%4
 elif a==5:
  if target!=(source+rotation)%4:return None
  proof=(source,target,origin,rotation)
 return source,target,origin,rotation,proof
def target(x):
 s=(0,0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FOUNDRY
  for i in range(4):
   f[9+i*9:15+i*9,8:25]=SOURCE if i==g.source else LANE
   f[9+i*9:15+i*9,39:56]=TARGET if i==g.target_relation else LANE+1
  f[48:51,8:8+g.origin*8]=FRAME;f[53:56,8:8+g.rotation*11]=TRANSFER
  if g.proof:f[44:58,57:60]=PROOF
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q655(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q655",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.source=self.target_relation=self.origin=self.rotation=0;self.proof=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.source,self.target_relation,self.origin,self.rotation,self.proof),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.source,self.target_relation,self.origin,self.rotation,self.proof=s
  elif a==6:
   if (self.source,self.target_relation,self.origin,self.rotation,self.proof)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
