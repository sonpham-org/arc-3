"""q170 Commit Threshold -- learn how much evidence each decision requires."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CHAMBER,EVIDENCE,DECISION,SAMPLE,THRESHOLD,COMMIT,GOAL,BAD=5,10,9,14,6,12,11,7,15
LEVELS=[{"name":"First Threshold","thresholds":(2,4,5),"plan":(2,5)},{"name":"Changed Decision","thresholds":(5,3,6),"plan":(4,3,1,5)},{"name":"Third Choice","thresholds":(6,7,5),"plan":(4,4,3,2,5)},{"name":"Higher Bar","thresholds":(7,6,8),"plan":(4,3,2,1,5)},{"name":"Delayed Commit","thresholds":(8,7,9),"plan":(4,4,3,3,3,5)},{"name":"Commit Threshold","thresholds":(10,9,11),"plan":(3,3,3,1,5)}]
def advance(s,a,x):
 evidence,decision,samples,committed=s;samples=list(samples)
 if a in (1,2,3):evidence+=a;samples.append((decision,a,evidence))
 elif a==4:decision=(decision+1)%3;evidence=max(0,evidence-1);samples.append((3,decision,evidence))
 elif a==5:
  if evidence<x["thresholds"][decision]:return None
  committed=(decision,evidence,tuple(samples))
 return evidence,decision,tuple(samples),committed
def target(x):
 s=(0,0,(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CHAMBER
  f[10:18,8:56]=EVIDENCE;f[10:18,8:8+min(g.evidence,12)*4]=SAMPLE
  for i in range(3):x=9+i*17;f[27:38,x:x+13]=DECISION-i
  f[42:45,8:11+g.decision*14]=THRESHOLD;f[52:55,8:24]=COMMIT if g.committed else EVIDENCE;f[56:59,44:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q170(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q170",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.evidence=self.decision=0;self.samples=();self.committed=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.evidence,self.decision,self.samples,self.committed),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.evidence,self.decision,self.samples,self.committed=s
  elif a==6:
   if (self.evidence,self.decision,self.samples,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
