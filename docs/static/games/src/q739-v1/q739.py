"""q739 Monsoon Gradient -- route conserved rain mass at unequal weather-clock phases."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,RAIN,STORM,FLOW,FAST,SLOW,GOAL,BAD=7,10,14,9,6,11,12,13,15
LEVELS=[
 {"name":"First Cell","seq":(1,)},{"name":"Reverse Front","seq":(2,1)},
 {"name":"Fast Phase","seq":(3,1,2)},{"name":"Slow Phase","seq":(1,3,2,1)},
 {"name":"Conserved Storm","seq":(2,3,1,2,3,1)},
 {"name":"Monsoon Gradient","seq":(1,2,3,1,3,2,1,2,3)}]
def advance(s,a):
 bins,fast,slow,front,locked=s;b=list(bins)
 if a==1:
  i=fast%4;j=(i+1+front)%4;n=min(b[i],1+slow%2);b[i]-=n;b[j]+=n;fast=(fast+1)%4
 elif a==2:
  front^=1;i=(fast+2)%4;j=(i-1-front)%4;n=min(b[i],1+fast%2);b[i]-=n;b[j]+=n;slow=(slow+1)%5
 elif a==3:fast=(fast+1)%4;slow=(slow+int(fast==0))%5
 elif a==4:b=b[1:]+b[:1];front^=1
 elif a==5:locked=(tuple(b),fast,slow,front)
 return tuple(b),fast,slow,front,locked
for x in LEVELS:
 s=((4,3,2,1),0,0,0,None)
 for a in x["seq"]:s=advance(s,a);assert sum(s[0])==10
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GARDEN
  for i,v in enumerate(g.bins):
   x=7+i*14;f[9:38,x:x+10]=STORM if i==g.fast else FLOW
   if v:f[35-v*5:35,x+2:x+8]=RAIN
  for i in range(7):x=8+i*7;f[42+(i%2)*4:45+(i%2)*4,x:x+5]=FLOW
  f[51:55,8:8+g.fast*12+8]=FAST;f[56:60,8:8+g.slow*9+7]=SLOW
  if g.locked:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q739(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q739",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=(4,3,2,1);self.fast=self.slow=self.front=0;self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.bins,self.fast,self.slow,self.front,self.locked=advance((self.bins,self.fast,self.slow,self.front,self.locked),a)
  elif a==6:
   if (self.bins,self.fast,self.slow,self.front,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
