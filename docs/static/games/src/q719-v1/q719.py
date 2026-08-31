"""q719 Strata Gradient -- route conserved ore while reversible probes leave persistent knowledge."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,QUARRY,ORE,FAULT,FLOW,PROBE,EVIDENCE,GOAL,BAD=7,10,14,9,6,11,12,13,15
LEVELS=[
 {"name":"First Transfer","seq":(1,)},{"name":"Reverse Fault","seq":(2,1)},
 {"name":"Knowledge Probe","seq":(3,1,2)},{"name":"Persistent Gradient","seq":(1,3,2,1)},
 {"name":"Conserved Ore","seq":(2,3,1,2,3,1)},
 {"name":"Strata Gradient","seq":(1,2,3,1,3,2,1,2,3)}]
def advance(s,a):
 bins,phase,fault,evidence,locked=s;b=list(bins)
 if a==1:
  i=phase%4;j=(i+1+fault)%4;n=min(b[i],1+fault);b[i]-=n;b[j]+=n;phase=(phase+1)%4
 elif a==2:
  fault^=1;i=(phase+2)%4;j=(i-1-fault)%4;n=min(b[i],1+phase%2);b[i]-=n;b[j]+=n
 elif a==3:evidence=evidence+((tuple(b),phase,fault),);phase=(phase+1)%4
 elif a==4:b=b[1:]+b[:1];fault^=1
 elif a==5:locked=(tuple(b),phase,fault,evidence[-3:])
 return tuple(b),phase,fault,evidence,locked
for x in LEVELS:
 s=((4,3,2,1),0,0,(),None)
 for a in x["seq"]:s=advance(s,a);assert sum(s[0])==10
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=QUARRY
  for i,v in enumerate(g.bins):
   x=7+i*14;f[9:38,x:x+10]=FAULT if i==g.phase else FLOW
   if v:f[35-v*5:35,x+2:x+8]=ORE
  for i,e in enumerate(g.evidence[-4:]):x=8+i*12;f[42:47,x:x+9]=EVIDENCE;f[48:50,x:x+2+e[2]*3]=PROBE
  f[54:58,8:8+g.fault*25+12]=FAULT
  if g.locked:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q719(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q719",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=(4,3,2,1);self.phase=self.fault=0;self.evidence=();self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.bins,self.phase,self.fault,self.evidence,self.locked=advance((self.bins,self.phase,self.fault,self.evidence,self.locked),a)
  elif a==6:
   if (self.bins,self.phase,self.fault,self.evidence,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
