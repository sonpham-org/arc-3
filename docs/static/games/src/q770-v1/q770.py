"""q770 Workbench Obligation -- repay helper-bound tool debt after fixtures reconfigure."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SHOP,BENCH,TOOL,FIXTURE,HELPER,DEBT,GOAL,BAD=7,10,5,14,8,11,12,13,15
LEVELS=[{"name":"Borrowed Tool","seq":(1,)},{"name":"Fixture Swap","seq":(2,1)},{"name":"Helper Return","seq":(3,1,2)},{"name":"Reconfigured Bench","seq":(4,2,1,3)},{"name":"Delayed Favor","seq":(2,3,1,4,2,1)},{"name":"Workbench Obligation","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 helpers,tools,debt,fixture,favors,history,settled=s;h=list(helpers);t=list(tools);d=list(debt)
 if a==1:i=h[fixture%3];d[i]+=1;t[i]=(t[i]+1+fixture)%5;favors+=1;history=history+((i,1,fixture),)
 elif a==2:h[0],h[2]=h[2],h[0];t[0],t[2]=t[2],t[0];fixture=(fixture+1)%4
 elif a==3:i=h[(fixture+1)%3];d[i]=max(0,d[i]-1);favors=max(0,favors-1);history=history+((i,-1,fixture),)
 elif a==4:fixture=(fixture+2+favors)%4;t=t[1:]+t[:1]
 elif a==5:settled=(tuple(h),tuple(t),tuple(d),fixture,favors,history[-5:])
 return tuple(h),tuple(t),tuple(d),fixture,favors,history,settled
for x in LEVELS:
 s=((0,1,2),(0,2,4),(0,0,0),0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SHOP;f[8:31,7:57]=BENCH
  for lane,i in enumerate(g.helpers):x=9+i*17;f[23-g.tools[i]*3:29,x:x+11]=TOOL;f[10:16,x+2:x+9]=HELPER;f[17:20,x:x+11]=FIXTURE if lane==g.fixture%3 else BENCH
  for i,d in enumerate(g.debt):x=9+i*17;f[36:42,x:x+12]=DEBT;f[43:46,x:x+2+d*3]=TOOL
  f[51:55,8:8+g.fixture*11+8]=FIXTURE;f[56:59,8:8+min(5,g.favors)*9]=HELPER
  if g.settled:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q770(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q770",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.helpers=(0,1,2);self.tools=(0,2,4);self.debt=(0,0,0);self.fixture=self.favors=0;self.history=();self.settled=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.helpers,self.tools,self.debt,self.fixture,self.favors,self.history,self.settled=advance((self.helpers,self.tools,self.debt,self.fixture,self.favors,self.history,self.settled),a)
  elif a==6:
   if (self.helpers,self.tools,self.debt,self.fixture,self.favors,self.history,self.settled)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
