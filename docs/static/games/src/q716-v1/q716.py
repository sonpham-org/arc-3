"""q716 Palimpsest Gradient -- use a visible near miss to cross a conserved threshold."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,SHELF,TILE,PHASE,FAIL,THRESHOLD,COMMIT,BAD=4,8,11,6,2,15,9,13,10
LEVELS=[
 {"name":"Left Near Miss","initial":(1,1,0),"threshold":4,"plan":(4,1,5)},
 {"name":"Right Near Miss","initial":(0,2,0),"threshold":5,"plan":(4,2,5)},
 {"name":"Phase Difference","initial":(1,1,0),"threshold":5,"plan":(4,3,1,5)},
 {"name":"Composed Gradient","initial":(2,1,0),"threshold":7,"plan":(4,1,1,2,5)},
 {"name":"Conserved Crossing","initial":(2,2,0),"threshold":10,"plan":(4,1,1,2,3,5)},
 {"name":"Palimpsest Gradient","initial":(3,2,0),"threshold":13,"plan":(4,1,1,1,2,2,3,5)}]
def measure(bins,phase):return bins[0]+2*bins[1]+3*bins[2]+phase
def advance(s,a,x):
 bins,phase,failure,committed=s;bins=list(bins)
 if committed is not None:return None
 if a==1:
  if bins[0]<=0:return None
  bins[0]-=1;bins[1]+=1
 elif a==2:
  if bins[1]<=0:return None
  bins[1]-=1;bins[2]+=1
 elif a==3:phase=(phase+1)%4
 elif a==4:
  now=measure(bins,phase)
  if now>=x["threshold"]:return None
  failure=(now,x["threshold"]-now)
 elif a==5:
  now=measure(bins,phase)
  if failure is None or now<x["threshold"]:return None
  committed=(tuple(bins),phase,now,failure)
 return tuple(bins),phase,failure,committed
def target(x):
 s=(x["initial"],0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ARCHIVE
  for i,v in enumerate(g.bins):x=8+i*17;f[8:35,x:x+13]=SHELF+i%2;f[31-v*5:33,x+2:x+11]=TILE+i
  f[41:45,8:8+g.phase*11]=PHASE;f[48:51,8:56]=THRESHOLD
  if g.failure:f[53:57,8:8+min(g.failure[1],8)*6]=FAIL
  if g.committed:f[38:58,56:59]=COMMIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q716(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q716",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=self.cfg["initial"];self.phase=0;self.failure=self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.bins,self.phase,self.failure,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.bins,self.phase,self.failure,self.committed=s
  elif a==6:
   if (self.bins,self.phase,self.failure,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
