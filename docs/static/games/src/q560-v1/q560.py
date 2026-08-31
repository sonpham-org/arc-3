"""q560 Workbench Lesson -- infer a contextual tool policy while tracking helper debt."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SHOP,BENCH,TOOL,FIXTURE,DEMO,DEBT,GOAL,BAD=0,9,7,14,10,6,12,13,15
LEVELS=[{"name":"Shown Tool","seq":(1,)},{"name":"Fixture Context","seq":(4,2)},{"name":"Harmless Gesture","seq":(1,3,2)},{"name":"Helper Identity","seq":(2,4,1,3)},{"name":"Conditional Workshop","seq":(1,4,2,3,2,1)},{"name":"Workbench Lesson","seq":(2,1,3,4,2,4,1,3,2)}]
def advance(s,a):
 context,tools,fixture,trace,debt,policy=s;v=list(tools)
 if a==1:v[context],v[(context+1)%3]=v[(context+1)%3],v[context];fixture=(fixture+1+context)%4;trace=trace+((context,1,tuple(v)),);debt=(debt[0]+1,debt[1])
 elif a==2:v=v[1:]+v[:1];fixture=(fixture+2+context)%4;trace=trace+((context,2,tuple(v)),);debt=(debt[0],debt[1]+1)
 elif a==3:trace=trace+((context,0,tuple(v)),)
 elif a==4:context=(context+1)%3;fixture=(fixture+context)%4
 elif a==5:policy=(context,tuple(v),fixture,trace[-4:],debt)
 return context,tuple(v),fixture,trace,debt,policy
for x in LEVELS:
 s=(0,(0,1,2),0,(),(0,0),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SHOP;f[8:31,7:57]=BENCH
  for i,v in enumerate(g.tools):x=10+i*16;f[23-v*4:29,x:x+10]=FIXTURE;f[12:18,x+2:x+8]=TOOL if i==g.context else DEMO
  for i,(_,a,v) in enumerate(g.trace[-4:]):x=8+i*12;f[36:42,x:x+9]=DEMO if a else DEBT;f[43:46,x:x+2+v[0]*2]=TOOL
  f[50:54,8:8+g.fixture*11+8]=FIXTURE;f[56:60,8:8+min(6,sum(g.debt))*7]=DEBT
  if g.policy:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q560(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q560",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.context=0;self.tools=(0,1,2);self.fixture=0;self.trace=();self.debt=(0,0);self.policy=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.context,self.tools,self.fixture,self.trace,self.debt,self.policy=advance((self.context,self.tools,self.fixture,self.trace,self.debt,self.policy),a)
  elif a==6:
   if (self.context,self.tools,self.fixture,self.trace,self.debt,self.policy)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
