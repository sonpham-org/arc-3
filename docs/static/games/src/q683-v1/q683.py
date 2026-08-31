"""q683 Ember Evidence -- spend finite effort calibrating only decisive observations."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,EVIDENCE,SAMPLE,CALIBRATE,STOP,RESOURCE,BAD=15,8,2,6,11,4,10,13
LEVELS=[
 {"name":"Dominant Firing","weights":(5,1,1),"plan":(1,5),"budget":4},
 {"name":"Second Vessel","weights":(1,5,1),"plan":(2,5),"budget":4},
 {"name":"Resolve the Tie","weights":(4,3,1),"plan":(1,2,3,5),"budget":6},
 {"name":"Calibrated First","weights":(3,2,1),"plan":(4,1,5),"budget":5},
 {"name":"Calibrated Second","weights":(2,5,1),"plan":(4,4,2,5),"budget":6},
 {"name":"Ember Evidence","weights":(5,4,6),"plan":(4,4,4,3,5),"budget":7}]
def advance(s,a,x):
 scores,sampled,cal,resource,stopped=s;scores=list(scores);sampled=list(sampled)
 if resource<=0:return None
 resource-=1
 if a in (1,2,3):
  i=a-1
  if i in sampled:return None
  sampled.append(i);scores[i]+=x["weights"][i]*(2 if cal==i else 1)
 elif a==4:cal=(cal+1)%3
 elif a==5:
  if not sampled:return None
  order=sorted(scores,reverse=True);margin=order[0]-order[1];remaining=sum(x["weights"][i]*(2 if cal==i else 1) for i in range(3) if i not in sampled)
  if margin<=remaining:return None
  stopped=(scores.index(max(scores)),tuple(scores),tuple(sampled),cal,remaining)
 return tuple(scores),tuple(sampled),cal,resource,stopped
def target(x):
 s=((0,0,0),(),-1,x["budget"],None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=KILN
  for i,v in enumerate(g.scores):
   x=9+i*17;f[31-v*2:33,x:x+12]=EVIDENCE-i;f[10:14,x:x+12]=CALIBRATE if g.cal==i else SAMPLE
  f[40:44,8:8+len(g.sampled)*14]=SAMPLE;f[49:53,8:8+g.resource*6]=RESOURCE
  if g.stopped:f[55:59,42:56]=STOP
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q683(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q683",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.scores=(0,0,0);self.sampled=();self.cal=-1;self.resource=self.cfg["budget"];self.stopped=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.scores,self.sampled,self.cal,self.resource,self.stopped),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.scores,self.sampled,self.cal,self.resource,self.stopped=s
  elif a==6:
   if (self.scores,self.sampled,self.cal,self.resource,self.stopped)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
