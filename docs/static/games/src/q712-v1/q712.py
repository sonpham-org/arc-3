"""q712 Tide Gradient -- shape conserved influence before an irreversible threshold crossing."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BASIN,CURRENT,SHELL,DENSITY,PHASE,EVIDENCE,COMMIT,BAD=6,10,9,14,12,5,11,7,15
LEVELS=[{"name":"First Current","capacity":7,"threshold":12,"plan":(1,4,5)},{"name":"Reversing Pair","capacity":7,"threshold":12,"plan":(2,1,4,5)},{"name":"Conserved Slope","capacity":7,"threshold":12,"plan":(3,2,1,4,5)},{"name":"Phase Capacity","capacity":6,"threshold":12,"plan":(1,3,2,4,5)},{"name":"Second Measure","capacity":7,"threshold":12,"plan":(2,1,4,3,2,4,5)},{"name":"Tide Gradient","capacity":7,"threshold":12,"plan":(3,1,2,4,2,1,4,5)}]
def metric(dist,phase):return sum((i+1)*v for i,v in enumerate(dist))+phase
def advance(s,a,x):
 dist,phase,evidence,irreversible=s;dist=list(dist)
 if a in (1,2,3):
  src=a-1;dst=(src+phase+1)%3
  if dist[src]:dist[src]-=1;dist[dst]+=1
  phase=(phase+1)%3
 elif a==4:evidence=(tuple(dist),phase,metric(dist,phase),sum(dist))
 elif a==5:
  if evidence is None or max(dist)>x["capacity"] or metric(dist,phase)<x["threshold"]:return None
  irreversible=(tuple(dist),phase,evidence,metric(dist,phase))
 return tuple(dist),phase,evidence,irreversible
def target(x):
 s=((4,3,2),0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BASIN
  for i,v in enumerate(g.dist):x=8+i*18;f[8:33,x:x+14]=CURRENT;f[26-v*3:29,x+3:x+11]=SHELL-i;f[36:39,x:x+v*3]=DENSITY
  f[45:48,8:11+g.phase*14]=PHASE;f[51:54,8:24]=EVIDENCE if g.evidence else CURRENT;f[56:59,44:56]=COMMIT if g.irreversible else BASIN
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q712(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q712",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.dist=(4,3,2);self.phase=0;self.evidence=self.irreversible=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.dist,self.phase,self.evidence,self.irreversible),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.dist,self.phase,self.evidence,self.irreversible=s
  elif a==6:
   if (self.dist,self.phase,self.evidence,self.irreversible)==self.target and sum(self.dist)==9:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
