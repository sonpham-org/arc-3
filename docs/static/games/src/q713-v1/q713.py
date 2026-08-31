"""q713 Ember Gradient -- conserve mass while heat and phase set a commit threshold."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,BIN,MASS,HEAT,PHASE,OBSERVE,COMMIT,RESOURCE,BAD=0,9,8,6,2,11,4,7,10,15
LEVELS=[
 {"name":"Left Influence","initial":(1,2,0),"threshold":4,"plan":(1,4,5),"budget":5},
 {"name":"Right Influence","initial":(2,1,0),"threshold":6,"plan":(2,4,5),"budget":5},
 {"name":"Heat Phase","initial":(1,2,0),"threshold":7,"plan":(3,4,5),"budget":5},
 {"name":"Coupled Gradient","initial":(2,2,0),"threshold":7,"plan":(1,3,4,5),"budget":6},
 {"name":"Conserved Threshold","initial":(2,2,0),"threshold":12,"plan":(1,2,3,3,4,5),"budget":8},
 {"name":"Ember Gradient","initial":(2,3,0),"threshold":13,"plan":(1,1,2,3,3,4,5),"budget":9}]
def influence(bins,heat,phase):return bins[0]+2*bins[1]+3*bins[2]+heat+phase
def advance(s,a,x):
 bins,heat,phase,observed,resource,committed=s;bins=list(bins)
 if resource<=0 or committed is not None:return None
 resource-=1
 if a==1:
  if bins[1]<=0:return None
  bins[1]-=1;bins[0]+=1
 elif a==2:
  if bins[0]<=0:return None
  bins[0]-=1;bins[2]+=1
 elif a==3:phase=(phase+heat+1)%5;heat=(heat+1)%4
 elif a==4:observed=influence(bins,heat,phase)
 elif a==5:
  now=influence(bins,heat,phase)
  if observed!=now or now<x["threshold"]:return None
  committed=(tuple(bins),heat,phase,now)
 return tuple(bins),heat,phase,observed,resource,committed
def target(x):
 s=(x["initial"],0,0,None,x["budget"],None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[3:61,3:61]=KILN
  for i,v in enumerate(g.bins):x=8+i*17;f[12:36,x:x+13]=BIN;f[33-v*5:34,x+2:x+11]=MASS+i
  f[41:45,8:8+g.heat*10]=HEAT;f[47:51,8:8+g.phase*8]=PHASE;f[53:57,8:8+g.resource*5]=RESOURCE
  if g.observed is not None:f[7:10,8:8+min(g.observed,15)*3]=OBSERVE
  if g.committed:f[39:59,56:59]=COMMIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q713(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q713",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=self.cfg["initial"];self.heat=self.phase=0;self.observed=None;self.resource=self.cfg["budget"];self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.bins,self.heat,self.phase,self.observed,self.resource,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.bins,self.heat,self.phase,self.observed,self.resource,self.committed=s
  elif a==6:
   if (self.bins,self.heat,self.phase,self.observed,self.resource,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
