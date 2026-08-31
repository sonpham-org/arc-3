"""q681 Aurora Evidence -- stop when no remaining unequal sample can change the action."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,OBSERVATORY,CURTAIN,MOTE,EVIDENCE,RELIABILITY,HYSTERESIS,STOP,BAD=5,10,12,14,6,11,4,7,15
LEVELS=[{"name":"Dominant Sample","weights":(5,1,1),"plan":(1,5)},{"name":"Second Candidate","weights":(1,5,1),"plan":(2,5)},{"name":"Close Evidence","weights":(4,3,1),"plan":(1,2,3,5)},{"name":"Context Return","weights":(6,1,1),"plan":(4,1,5)},{"name":"Unequal Reliability","weights":(2,8,1),"plan":(4,2,5)},{"name":"Aurora Evidence","weights":(5,4,3),"plan":(4,1,2,3,5)}]
def advance(s,a,x):
 scores,sampled,context,hyst,stopped=s;scores=list(scores);sampled=list(sampled)
 if a in (1,2,3):
  i=a-1
  if i in sampled:return None
  sampled.append(i);scores[i]+=x["weights"][i]+hyst%2
 elif a==4:context=(context-1)%3;hyst=(hyst+2)%5
 elif a==5:
  order=sorted(scores,reverse=True);margin=order[0]-order[1];remaining=sum(x["weights"][i]+1 for i in range(3) if i not in sampled)
  if margin<=remaining:return None
  stopped=(scores.index(max(scores)),tuple(scores),tuple(sampled),remaining,context,hyst)
 return tuple(scores),tuple(sampled),context,hyst,stopped
def target(x):
 s=((0,0,0),(),0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=OBSERVATORY;f[8:31,7:57]=CURTAIN
  for i,v in enumerate(g.scores):x=9+i*17;f[26-v*3:28,x:x+13]=EVIDENCE-i;f[10:14,x:x+13]=RELIABILITY-i
  f[38:41,8:11+g.context*14]=MOTE;f[45:48,8:11+g.hyst*9]=HYSTERESIS;f[54:57,40:56]=STOP if g.stopped else CURTAIN
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q681(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q681",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.scores=(0,0,0);self.sampled=();self.context=self.hyst=0;self.stopped=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.scores,self.sampled,self.context,self.hyst,self.stopped),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.scores,self.sampled,self.context,self.hyst,self.stopped=s
  elif a==6:
   if (self.scores,self.sampled,self.context,self.hyst,self.stopped)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
