"""q727 Catalyst Gradient -- observe a pipe direction and hide-execute its conserved transfer."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,REFINERY,BIN0,BIN1,BIN2,MEMORY,PHASE,GOAL,BAD=6,12,9,14,10,11,8,13,15
LEVELS=[
 {"name":"First Transfer","initial":(2,0,0),"transfers":(0,)},{"name":"Repeated Transfer","initial":(3,0,0),"transfers":(0,0)},
 {"name":"Two Pipes","initial":(3,0,0),"transfers":(0,1)},{"name":"Stored Gradient","initial":(3,1,0),"transfers":(0,1,0)},
 {"name":"Circular Flow","initial":(3,1,1),"transfers":(0,1,0,2)},{"name":"Catalyst Gradient","initial":(4,2,1),"transfers":(0,1,0,2,1)}]
def make_plan(transfers):
 selector=phase=0;p=[]
 for desired in transfers:
  turns=(desired-phase-selector)%3;p.extend((1,)*turns);selector=(selector+turns)%3;p.extend((3,4));phase=(phase+1)%3
 return tuple(p)+(5,)
for x in LEVELS:x["plan"]=make_plan(x["transfers"])
def advance(s,a,x):
 bins,selector,memory,phase,visible,done=s;b=list(bins)
 if a==1:selector=(selector+1)%3
 elif a==2:phase=(phase+1)%3
 elif a==3:memory=(selector+phase)%3;visible=1
 elif a==4:
  if memory is None:return None
  src,dst=memory,(memory+1)%3
  if not b[src] or b[dst]>=5:return None
  b[src]-=1;b[dst]+=1;phase=(phase+1)%3;visible=0
 elif a==5:done=(tuple(b),phase)
 return tuple(b),selector,memory,phase,visible,done
def target(x):
 s=(x["initial"],0,None,0,1,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=REFINERY
  for i,c in enumerate((BIN0,BIN1,BIN2)):
   x=8+i*17;f[8:33,x:x+14]=c;f[29-g.bins[i]*3:29,x+3:x+11]=GOAL
  f[38:42,8:8+g.selector*15]=MEMORY;f[46:50,8:8+g.phase*15]=PHASE
  if g.memory is not None:f[53:57,8:8+g.memory*15]=MEMORY
  if g.done:f[54:59,39:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q727(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q727",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=self.cfg["initial"];self.selector=self.phase=0;self.memory=self.done=None;self.visible=1
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.bins,self.selector,self.memory,self.phase,self.visible,self.done),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.bins,self.selector,self.memory,self.phase,self.visible,self.done=s
  elif a==6:
   if (self.bins,self.selector,self.memory,self.phase,self.visible,self.done)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
