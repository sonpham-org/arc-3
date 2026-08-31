"""q710 Workbench Evidence -- stop sampling when no fixture result can change the decision."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SHOP,FIXTURE,TOOL,SAMPLE,MARGIN,COST,GOAL,BAD=6,12,10,14,8,11,9,13,15
LEVELS=[
 {"name":"One Sample","seq":(1,)},{"name":"Unequal Weight","seq":(2,1)},
 {"name":"Fixture Test","seq":(3,1,2)},{"name":"Bounded Margin","seq":(1,3,2,1)},
 {"name":"Costly Evidence","seq":(2,3,1,2,3,1)},
 {"name":"Workbench Evidence","seq":(1,2,3,1,3,2,1,2,3)}]
def advance(s,a):
 margin,samples,fixture,cost,stopped=s
 if a==1:margin+=2+fixture;samples=samples+((1,fixture),);cost+=1
 elif a==2:margin-=1+fixture%2;samples=samples+((-1,fixture),);cost+=2
 elif a==3:fixture=(fixture+1)%4;margin+=fixture-1
 elif a==4:margin=max(-9,min(9,2*margin));cost+=1
 elif a==5:stopped=(margin,samples[-4:],fixture,cost,int(abs(margin)>cost//3))
 return margin,samples,fixture,cost,stopped
for x in LEVELS:
 s=(0,(),0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SHOP
  for i in range(4):
   x=7+i*14;f[9:28,x:x+10]=FIXTURE if i==g.fixture else COST;f[14:23,x+3:x+7]=TOOL
  for i,(sign,fix) in enumerate(g.samples[-6:]):
   x=8+i*8;f[34:40,x:x+6]=SAMPLE if sign>0 else COST;f[41:44,x:x+2+fix]=FIXTURE
  center=31;lo=min(center,center+g.margin*2);hi=max(center,center+g.margin*2);f[48:53,lo:hi+1]=MARGIN
  f[55:59,8:8+min(g.cost,10)*4]=COST
  if g.stopped:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q710(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q710",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.margin=self.fixture=self.cost=0;self.samples=();self.stopped=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.margin,self.samples,self.fixture,self.cost,self.stopped=advance((self.margin,self.samples,self.fixture,self.cost,self.stopped),a)
  elif a==6:
   if (self.margin,self.samples,self.fixture,self.cost,self.stopped)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
