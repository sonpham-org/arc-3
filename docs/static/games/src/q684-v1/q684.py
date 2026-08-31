"""q684 Honeycomb Evidence -- stop only when unequal samples and nested clocks agree."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HIVE,CELL,EVIDENCE,SAMPLE,LOCAL,OUTER,STOP,BAD=7,8,12,6,2,4,9,13,15
LEVELS=[
 {"name":"First Shared Stop","weights":(5,1,1),"cycle":2,"plan":(1,4,5)},
 {"name":"Second Shared Stop","weights":(1,5,1),"cycle":2,"plan":(2,4,5)},
 {"name":"Resolve Every Sample","weights":(4,3,1),"cycle":4,"plan":(1,2,3,4,5)},
 {"name":"Three-Step Clock","weights":(6,1,1),"cycle":3,"plan":(1,4,4,5)},
 {"name":"Unequal Reliability","weights":(6,3,1),"cycle":4,"plan":(1,2,4,4,5)},
 {"name":"Honeycomb Evidence","weights":(5,4,3),"cycle":5,"plan":(1,2,3,4,4,5)}]
def advance(s,a,x):
 scores,sampled,local,outer,stopped=s;scores=list(scores);sampled=list(sampled)
 if a in (1,2,3):
  i=a-1
  if i in sampled:return None
  sampled.append(i);scores[i]+=x["weights"][i];local+=1
 elif a==4:local+=1
 elif a==5:
  if local:return None
  order=sorted(scores,reverse=True);margin=order[0]-order[1];remaining=sum(x["weights"][i] for i in range(3) if i not in sampled)
  if margin<=remaining:return None
  stopped=(scores.index(max(scores)),tuple(scores),tuple(sampled),outer,remaining)
 if local>=x["cycle"]:outer+=local//x["cycle"];local%=x["cycle"]
 return tuple(scores),tuple(sampled),local,outer,stopped
def target(x):
 s=((0,0,0),(),0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HIVE
  for i,v in enumerate(g.scores):x=8+i*17;f[8:35,x:x+13]=CELL+i%2;f[31-v*3:33,x+2:x+11]=EVIDENCE-i
  f[41:45,8:8+len(g.sampled)*14]=SAMPLE;f[48:51,8:8+g.local*8]=LOCAL;f[53:56,8:8+g.outer*8]=OUTER
  if g.stopped:f[38:58,56:59]=STOP
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q684(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q684",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.scores=(0,0,0);self.sampled=();self.local=self.outer=0;self.stopped=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.scores,self.sampled,self.local,self.outer,self.stopped),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.scores,self.sampled,self.local,self.outer,self.stopped=s
  elif a==6:
   if (self.scores,self.sampled,self.local,self.outer,self.stopped)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
