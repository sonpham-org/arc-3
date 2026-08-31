"""q740 Workbench Gradient -- route conserved tool mass through capacity-limited fixtures."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SHOP,FIXTURE,TOOL,FLOW,CAPACITY,DEBT,GOAL,BAD=7,13,11,14,6,10,9,12,15
LEVELS=[
 {"name":"First Transfer","seq":(1,)},{"name":"Reverse Gradient","seq":(2,1)},
 {"name":"Phase Capacity","seq":(3,1,2)},{"name":"Borrowed Tool","seq":(4,1,3,2)},
 {"name":"Conserved Route","seq":(1,3,2,4,1,2)},
 {"name":"Workbench Gradient","seq":(3,1,4,2,3,1,2,4,1)}]
def advance(s,a):
 bins,phase,fixture,debt,locked=s;b=list(bins)
 if a==1:
  i=phase%4;j=(i+1)%4;amount=min(b[i],1+fixture%2);b[i]-=amount;b[j]+=amount
 elif a==2:
  i=(phase+2)%4;j=(i-1)%4;amount=min(b[i],1+(phase%2));b[i]-=amount;b[j]+=amount
 elif a==3:phase=(phase+1)%4;fixture=(fixture+phase)%4
 elif a==4:debt=(debt+1+phase)%4;fixture=(fixture+debt)%4
 elif a==5:locked=(tuple(b),phase,fixture,debt)
 return tuple(b),phase,fixture,debt,locked
for x in LEVELS:
 s=((4,3,2,1),0,0,0,None)
 for a in x["seq"]:s=advance(s,a);assert sum(s[0])==10
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SHOP
  for i,v in enumerate(g.bins):
   x=7+i*14;f[9:38,x:x+10]=FIXTURE if i==g.fixture else CAPACITY
   if v:f[35-v*5:35,x+2:x+8]=TOOL if i!=g.debt else DEBT
  f[43:48,8:8+g.phase*12+8]=FLOW;f[51:55,8:8+g.fixture*12+8]=CAPACITY
  if g.locked:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q740(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q740",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=(4,3,2,1);self.phase=self.fixture=self.debt=0;self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.bins,self.phase,self.fixture,self.debt,self.locked=advance((self.bins,self.phase,self.fixture,self.debt,self.locked),a)
  elif a==6:
   if (self.bins,self.phase,self.fixture,self.debt,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
