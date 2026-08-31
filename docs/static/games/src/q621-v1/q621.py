"""q621 Aurora Sandbox -- retain simulated evidence while discarding simulated progress."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,OBSERVATORY,CURTAIN,MOTE,SANDBOX,EVIDENCE,HYSTERESIS,COMMIT,BAD=3,10,12,14,6,11,4,7,15
LEVELS=[{"name":"Two Copies","plan":(1,2,5)},{"name":"Reset Copy","plan":(1,3,2,5)},{"name":"Context Shift","plan":(1,4,2,5)},{"name":"Persistent Evidence","plan":(1,2,3,4,1,2,5)},{"name":"Hysteretic Test","plan":(2,4,1,3,2,1,5)},{"name":"Aurora Sandbox","plan":(1,4,2,3,4,2,1,5)}]
def advance(s,a):
 copies,evidence,active,hyst,committed=s;copies=list(copies);evidence=list(evidence)
 if a in (1,2):i=a-1;copies[i]=(copies[i]+a+active+hyst)%6;evidence.append((i,copies[i],hyst))
 elif a==3:copies=[0,0]
 elif a==4:active=1-active;hyst=(hyst+active+2)%5
 elif a==5:
  if len({e[0] for e in evidence})<2:return None
  committed=(tuple(evidence),active,hyst,(sum(e[1] for e in evidence)+hyst)%4)
 return tuple(copies),tuple(evidence),active,hyst,committed
def target(x):
 s=((0,0),(),0,0,None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=OBSERVATORY;f[8:31,7:29]=SANDBOX;f[8:31,35:57]=CURTAIN
  for i,v in enumerate(g.copies):x=10+i*28;f[12+v*3:18+v*3,x:x+14]=MOTE-i
  for i,(_,v,_) in enumerate(g.evidence[-6:]):f[36+i*3:38+i*3,8:11+v*8]=EVIDENCE
  f[50:53,8:11+g.hyst*9]=HYSTERESIS;f[55:58,40:56]=COMMIT if g.committed else SANDBOX
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q621(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q621",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.copies=(0,0);self.evidence=();self.active=self.hyst=0;self.committed=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.copies,self.evidence,self.active,self.hyst,self.committed),a)
   if s is None:self.bad=True;self.lose()
   else:self.copies,self.evidence,self.active,self.hyst,self.committed=s
  elif a==6:
   if (self.copies,self.evidence,self.active,self.hyst,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
