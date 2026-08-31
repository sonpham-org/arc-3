"""q715 Alloy Gradient -- conserve billets while measuring influence in a rotating frame."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,LANE,BILLET,FORCE,PHASE,FRAME,COMMIT,BAD=10,1,8,6,2,11,13,4,15
LEVELS=[
 {"name":"Forward Influence","initial":(2,0,0,0),"threshold":4,"plan":(1,3,5)},
 {"name":"Reverse Influence","initial":(1,1,0,0),"threshold":3,"plan":(2,3,5)},
 {"name":"Rotated Lane","initial":(0,2,0,0),"threshold":4,"plan":(4,1,3,5)},
 {"name":"Moving Gradient","initial":(2,1,0,0),"threshold":8,"plan":(1,4,1,3,5)},
 {"name":"Conserved Orbit","initial":(3,1,0,0),"threshold":13,"plan":(1,4,1,4,1,3,5)},
 {"name":"Alloy Gradient","initial":(3,2,0,0),"threshold":18,"plan":(1,4,1,4,1,3,3,5)}]
def measure(lanes,rotation,phase):return sum(lanes[(rotation+i)%4]*(i+1) for i in range(4))+phase
def advance(s,a,x):
 lanes,origin,rotation,phase,signal,committed=s;lanes=list(lanes)
 if committed is not None:return None
 if a in (1,2):
  src=(rotation+(0 if a==1 else 1))%4;dst=(rotation+(1 if a==1 else 0))%4
  if lanes[src]<=0:return None
  lanes[src]-=1;lanes[dst]+=1
 elif a==3:phase=(phase+1)%4;signal=measure(lanes,rotation,phase)
 elif a==4:origin=(origin+1)%6;rotation=(rotation+1)%4;signal=None
 elif a==5:
  now=measure(lanes,rotation,phase)
  if signal!=now or now<x["threshold"]:return None
  committed=(tuple(lanes),origin,rotation,phase,now)
 return tuple(lanes),origin,rotation,phase,signal,committed
def target(x):
 s=(x["initial"],0,0,0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FOUNDRY
  for screen in range(4):
   x=7+screen*13;physical=(g.rotation+screen)%4;f[9:35,x:x+10]=LANE+screen%2;f[31-g.lanes[physical]*5:33,x+2:x+8]=BILLET+physical%3
  f[40:44,8:8+g.phase*11]=PHASE;f[47:50,8:8+g.origin*8]=FRAME
  if g.signal is not None:f[53:56,8:8+min(g.signal,16)*3]=FORCE
  if g.committed:f[38:58,56:59]=COMMIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q715(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q715",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.lanes=self.cfg["initial"];self.origin=self.rotation=self.phase=0;self.signal=self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.lanes,self.origin,self.rotation,self.phase,self.signal,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.lanes,self.origin,self.rotation,self.phase,self.signal,self.committed=s
  elif a==6:
   if (self.lanes,self.origin,self.rotation,self.phase,self.signal,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
