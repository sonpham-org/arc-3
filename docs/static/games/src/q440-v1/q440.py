"""q440 Workbench Revision -- revise a worn fixture and repay the original helper."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BENCH,FIXTURE,TOOL,WEAR,RULE,DEBT,REPAIR,BAD=7,10,9,14,12,5,11,6,15
LEVELS=[{"name":"First Wear","rule":1,"plan":(1,4,5)},{"name":"Moved Erratum","rule":2,"plan":(2,4,1,2,5)},{"name":"Third Helper","rule":3,"plan":(3,4,1,2,3,5)},{"name":"Two Revisions","rule":1,"plan":(1,4,2,4,1,5,2,5)},{"name":"Crossed Wear","rule":2,"plan":(2,4,3,4,1,2,5,3,5)},{"name":"Workbench Revision","rule":3,"plan":(1,4,2,4,3,4,3,5,2,5,1,5)}]
def advance(s,a,x):
 tools,selected,wear,debt,failed,repair=s;tools=list(tools);debt=list(debt)
 if a in (1,2,3):selected=a-1;tools[selected]=(tools[selected]+a+x["rule"]+wear)%5;wear=(wear+1)%4
 elif a==4:debt[selected]+=1;failed=(tuple(tools),wear,x["rule"],selected);wear=(wear+1)%4
 elif a==5:
  if not debt[selected] or failed is None:return None
  debt[selected]-=1
  if not sum(debt):repair=(failed,tuple(tools),wear)
 return tuple(tools),selected,wear,tuple(debt),failed,repair
def target(x):
 s=((0,2,4),0,0,(0,0,0),None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BENCH
  for i,v in enumerate(g.tools):x=8+i*18;f[8:35,x:x+14]=FIXTURE;f[12+v*4:18+v*4,x+4:x+10]=TOOL-i;f[38:41,x:x+g.debt[i]*6]=DEBT
  f[45:48,8:11+g.wear*11]=WEAR;f[51:54,8:24]=RULE;f[56:59,40:56]=REPAIR if g.repair else FIXTURE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q440(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q440",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.tools=(0,2,4);self.selected=self.wear=0;self.debt=(0,0,0);self.failed=self.repair=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.tools,self.selected,self.wear,self.debt,self.failed,self.repair),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.tools,self.selected,self.wear,self.debt,self.failed,self.repair=s
  elif a==6:
   if (self.tools,self.selected,self.wear,self.debt,self.failed,self.repair)==self.target and not sum(self.debt):self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
