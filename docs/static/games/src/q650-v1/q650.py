"""q650 Workbench Sandbox -- reset fixture trials while tool-debt evidence persists."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,SHOP,TOOL,FIXTURE,EVIDENCE,RESET,GOAL,BAD=4,9,11,14,10,6,12,13,15
LEVELS=[{"name":"First Trial","seq":(1,3)},{"name":"Reconfigured Fixture","seq":(2,3,4)},{"name":"Persistent Toolmark","seq":(1,3,4,2,3)},{"name":"Debt Contrast","seq":(2,1,3,4,1,3)},{"name":"Two Benches","seq":(1,2,3,4,2,2,3)},{"name":"Workbench Sandbox","seq":(2,1,3,4,1,2,3,4,2,3)}]
def advance(s,a):
 tools,fixture,debt,evidence,trials,commit=s;v=list(tools)
 if a==1:v[0],v[1]=v[1],v[0];fixture=(fixture+1)%4
 elif a==2:v=v[1:]+v[:1];debt=(debt+1+fixture)%5;fixture=(fixture+2)%4
 elif a==3:evidence=evidence+((tuple(v),fixture,debt),);trials+=1
 elif a==4:v[:]=[0,1,2];fixture=debt=0
 elif a==5:commit=(tuple(v),fixture,debt,evidence[-3:],trials)
 return tuple(v),fixture,debt,evidence,trials,commit
for x in LEVELS:
 s=((0,1,2),0,0,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB;f[8:31,7:29]=SHOP;f[8:31,35:57]=RESET
  for i,v in enumerate(g.tools):x=9+i*7;f[24-v*4:29,x:x+6]=TOOL
  for i,e in enumerate(g.evidence[-5:]):x=8+i*10;f[36:42,x:x+7]=EVIDENCE;f[43:46,x:x+2+e[2]]=FIXTURE
  f[50:54,8:8+g.fixture*11+7]=FIXTURE;f[55:59,8:8+g.debt*9+6]=EVIDENCE
  if g.commit:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q650(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q650",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.tools=(0,1,2);self.fixture=self.debt=self.trials=0;self.evidence=();self.commit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.tools,self.fixture,self.debt,self.evidence,self.trials,self.commit=advance((self.tools,self.fixture,self.debt,self.evidence,self.trials,self.commit),a)
  elif a==6:
   if (self.tools,self.fixture,self.debt,self.evidence,self.trials,self.commit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
