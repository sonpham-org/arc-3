"""q590 Workbench Counter -- shape a three-tactic rival before exploiting a fixture."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SHOP,FIXTURE,TOOL,RIVAL,HISTORY,EXPLOIT,GOAL,BAD=2,13,11,14,6,10,9,12,15
LEVELS=[
 {"name":"Visible Counter","seq":(1,)},{"name":"Two Treatments","seq":(2,1)},
 {"name":"Fixture Response","seq":(3,4,1)},{"name":"Shape Then Strike","seq":(1,2,4,3)},
 {"name":"Counter Cycle","seq":(2,3,1,4,2,1)},
 {"name":"Workbench Counter","seq":(3,1,2,4,1,3,2,4,1)}]
def advance(s,a):
 rival,history,fixture,tool,exploit=s
 if a in (1,2,3):
  history=(history+(a,))[-2:];rival=(sum(history)+fixture+tool)%3;tool=(tool+a+rival)%5
 elif a==4:fixture=(fixture+1+rival)%4;tool=(tool+fixture)%5
 elif a==5:exploit=(rival,fixture,tool,history)
 return rival,history,fixture,tool,exploit
for x in LEVELS:
 s=(0,(),0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SHOP
  for i in range(4):
   x=7+i*14;f[9:29,x:x+10]=FIXTURE if i==g.fixture else HISTORY
   f[14:24,x+3:x+7]=TOOL if i==(g.tool%4) else RIVAL
  for i,a in enumerate(g.history):f[35:42,9+i*20:22+i*20]=HISTORY;f[37:40,12+i*20:12+i*20+a*3]=TOOL
  f[47:52,8:8+g.rival*16+8]=RIVAL;f[54:58,8:8+g.tool*8+5]=TOOL
  if g.exploit:f[52:58,49:57]=EXPLOIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q590(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q590",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.rival=self.fixture=self.tool=0;self.history=();self.exploit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.rival,self.history,self.fixture,self.tool,self.exploit=advance((self.rival,self.history,self.fixture,self.tool,self.exploit),a)
  elif a==6:
   if (self.rival,self.history,self.fixture,self.tool,self.exploit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
