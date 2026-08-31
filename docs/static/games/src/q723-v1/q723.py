"""q723 Murmuration Gradient -- route conserved flock mass through wind wakes with parity."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,AVIARY,FLOCK,WIND,FLOW,CAPACITY,PARITY,GOAL,BAD=7,10,14,9,6,11,12,13,15
LEVELS=[
 {"name":"First Wake","seq":(1,)},{"name":"Reverse Wind","seq":(2,1)},
 {"name":"Parity Check","seq":(3,1,2)},{"name":"Capacity Turn","seq":(1,3,2,1)},
 {"name":"Conserved Flock","seq":(2,3,1,2,3,1)},
 {"name":"Murmuration Gradient","seq":(1,2,3,1,3,2,1,2,3)}]
def advance(s,a):
 bins,wind,phase,parity,locked=s;b=list(bins)
 if a==1:
  i=phase%4;j=(i+1+wind)%4;n=min(b[i],1+wind);b[i]-=n;b[j]+=n;parity^=(n%2)
 elif a==2:
  wind^=1;i=(phase+2)%4;j=(i-1-wind)%4;n=min(b[i],1+phase%2);b[i]-=n;b[j]+=n;parity^=(n%2)
 elif a==3:phase=(phase+1)%4;parity^=(phase%2)
 elif a==4:b=b[1:]+b[:1];wind^=1
 elif a==5:locked=(tuple(b),wind,phase,parity)
 return tuple(b),wind,phase,parity,locked
for x in LEVELS:
 s=((4,3,2,1),0,0,0,None)
 for a in x["seq"]:s=advance(s,a);assert sum(s[0])==10
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=AVIARY
  for i,v in enumerate(g.bins):
   x=7+i*14;f[9:38,x:x+10]=WIND if i==g.phase else CAPACITY
   if v:f[35-v*5:35,x+2:x+8]=FLOCK
  for i in range(7):x=8+i*7;f[41+(i%2)*4:44+(i%2)*4,x:x+5]=FLOW
  f[51:55,8:8+g.wind*25+12]=WIND;f[56:60,8:8+g.parity*25+12]=PARITY
  if g.locked:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q723(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q723",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=(4,3,2,1);self.wind=self.phase=self.parity=0;self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.bins,self.wind,self.phase,self.parity,self.locked=advance((self.bins,self.wind,self.phase,self.parity,self.locked),a)
  elif a==6:
   if (self.bins,self.wind,self.phase,self.parity,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
