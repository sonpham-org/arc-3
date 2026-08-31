"""q530 Workbench Frame -- compose tool motion across reconfigurable fixture frames and debt."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SHOP,FIXTURE,TOOL,FRAME,DEBT,LOCK,GOAL,BAD=0,8,11,14,6,10,12,13,15
LEVELS=[
 {"name":"Local Tool","seq":(1,)},{"name":"Rotated Fixture","seq":(2,1)},
 {"name":"Borrowed Frame","seq":(1,3,2)},{"name":"Translated Bench","seq":(2,1,4,3)},
 {"name":"Identity Fixture","seq":(1,2,3,4,1,2)},
 {"name":"Workbench Frame","seq":(2,1,4,3,2,1,3,4,1)}]
def advance(s,a):
 tool,fixture,rotation,debt,locked=s
 if a==1:tool=(tool+1+rotation+fixture)%8
 elif a==2:rotation=(rotation+1)%4;fixture=(fixture+rotation)%4
 elif a==3:debt=(tool+fixture+rotation)%6
 elif a==4:fixture=(fixture+2+debt)%4;tool=(tool+fixture)%8
 elif a==5:locked=(tool,fixture,rotation,debt)
 return tool,fixture,rotation,debt,locked
for x in LEVELS:
 s=(0,0,0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SHOP
  for i in range(4):x=7+i*14;f[8:29,x:x+10]=FIXTURE if i==g.fixture else FRAME;f[13+(i%2)*7:19+(i%2)*7,x+3:x+7]=TOOL
  for i in range(8):x=8+i*6;f[34:39,x:x+4]=TOOL if i==g.tool else FRAME
  f[45:50,8:8+g.debt*8+5]=DEBT;f[54:58,8:8+g.rotation*11+7]=LOCK
  if g.locked:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q530(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q530",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.tool=self.fixture=self.rotation=self.debt=0;self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.tool,self.fixture,self.rotation,self.debt,self.locked=advance((self.tool,self.fixture,self.rotation,self.debt,self.locked),a)
  elif a==6:
   if (self.tool,self.fixture,self.rotation,self.debt,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
