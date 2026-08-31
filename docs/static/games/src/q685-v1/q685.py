"""q685 Alloy Evidence -- stop safely when rotating screen slots hide causal candidates."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,LANE,EVIDENCE,SAMPLE,FRAME,STOP,BAD=9,1,11,6,2,13,4,15
LEVELS=[
 {"name":"Dominant Lane","weights":(5,1,1),"plan":(1,5)},
 {"name":"Second Lane","weights":(1,5,1),"plan":(2,5)},
 {"name":"Rotated Candidate","weights":(1,5,1),"plan":(4,1,5)},
 {"name":"Double Rotation","weights":(6,1,1),"plan":(4,4,2,5)},
 {"name":"Resolve Every Lane","weights":(4,3,1),"plan":(4,1,2,3,5)},
 {"name":"Alloy Evidence","weights":(5,4,3),"plan":(1,4,1,4,1,5)}]
def advance(s,a,x):
 scores,sampled,origin,rotation,stopped=s;scores=list(scores);sampled=list(sampled)
 if a in (1,2,3):
  causal=(a-1+rotation)%3
  if causal in sampled:return None
  sampled.append(causal);scores[causal]+=x["weights"][causal]
 elif a==4:origin=(origin+1)%6;rotation=(rotation+1)%3
 elif a==5:
  if not sampled:return None
  order=sorted(scores,reverse=True);margin=order[0]-order[1];remaining=sum(x["weights"][i] for i in range(3) if i not in sampled)
  if margin<=remaining:return None
  stopped=(scores.index(max(scores)),tuple(scores),tuple(sampled),origin,rotation,remaining)
 return tuple(scores),tuple(sampled),origin,rotation,stopped
def target(x):
 s=((0,0,0),(),0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FOUNDRY
  for screen in range(3):
   x=8+screen*17;causal=(screen+g.rotation)%3;f[8:35,x:x+13]=LANE+screen;v=g.scores[causal];f[31-v*3:33,x+2:x+11]=EVIDENCE-causal
  f[41:45,8:8+len(g.sampled)*14]=SAMPLE;f[48:51,8:8+g.origin*8]=FRAME;f[53:56,8:8+g.rotation*13]=EVIDENCE
  if g.stopped:f[39:58,56:59]=STOP
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q685(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q685",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.scores=(0,0,0);self.sampled=();self.origin=self.rotation=0;self.stopped=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.scores,self.sampled,self.origin,self.rotation,self.stopped),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.scores,self.sampled,self.origin,self.rotation,self.stopped=s
  elif a==6:
   if (self.scores,self.sampled,self.origin,self.rotation,self.stopped)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
