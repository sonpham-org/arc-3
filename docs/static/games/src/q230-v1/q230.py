"""q230 Workbench Veil -- schedule attention while repaying help to the original helper."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BENCH,FIXTURE,TOOL,FOCUS,HELPER,DEBT,GOAL,BAD=0,10,9,14,6,11,4,7,15
LEVELS=[{"name":"Borrowed Sight","plan":(1,4,5)},{"name":"Moved Favor","plan":(2,4,1,2,5)},{"name":"Hidden Helper","plan":(3,4,1,2,3,5)},{"name":"Two Favors","plan":(1,4,2,4,1,5,2,5)},{"name":"Crossed Debts","plan":(2,4,3,4,1,2,5,3,5)},{"name":"Workbench Veil","plan":(1,4,2,4,3,4,1,3,5,2,5,1,5)}]
def advance(s,a):
 tools,focus,phase,debt,borrowed=s;tools=list(tools);debt=list(debt)
 if a in (1,2,3):
  focus=a-1
  for i in range(3):
   if i!=focus:tools[i]=(tools[i]+phase+a+i)%6
  phase=(phase+1)%4
 elif a==4:debt[focus]+=1;tools[focus]=(tools[focus]+3+phase)%6;borrowed=(focus,tuple(tools))
 elif a==5:
  if not debt[focus]:return None
  debt[focus]-=1
 return tuple(tools),focus,phase,tuple(debt),borrowed
def target(x):
 s=((0,2,4),0,0,(0,0,0),None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BENCH
  for i,v in enumerate(g.tools):x=8+i*18;f[8:35,x:x+14]=FIXTURE;f[12+v*3:18+v*3,x+4:x+10]=TOOL-i;f[38:41,x:x+g.debt[i]*6]=DEBT
  f[6:9,8+g.focus*18:22+g.focus*18]=FOCUS;f[48:51,8:20]=HELPER if g.borrowed else FIXTURE;f[55:58,44:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q230(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q230",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.tools=(0,2,4);self.focus=self.phase=0;self.debt=(0,0,0);self.borrowed=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.tools,self.focus,self.phase,self.debt,self.borrowed),a)
   if s is None:self.bad=True;self.lose()
   else:self.tools,self.focus,self.phase,self.debt,self.borrowed=s
  elif a==6:
   if (self.tools,self.focus,self.phase,self.debt,self.borrowed)==self.target and not sum(self.debt):self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
