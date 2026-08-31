"""q620 Workbench Grammar -- compose tool messages while tracking identity-bound obligation."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SHOP,FIXTURE,TOOL,GROUP,RELAY,DEBT,GOAL,BAD=3,8,11,14,6,10,12,13,15
LEVELS=[
 {"name":"Tool Word","seq":(1,2,4)},{"name":"Fixture Phrase","seq":(2,3,4,5)},
 {"name":"Grouped Tool","seq":(1,3,2,4,4)},{"name":"Borrowed Relay","seq":(3,1,4,2,5,4)},
 {"name":"Obligation Message","seq":(1,2,4,3,5,2,4)},
 {"name":"Workbench Grammar","seq":(2,1,3,4,5,2,3,4,1,4)}]
def advance(s,a):
 stack,fixture,debt,history,locked=s;v=list(stack)
 if a in (1,2,3):v.append((a+fixture)%6)
 elif a==4:
  if len(v)<2:return None
  b=v.pop();c=v.pop();v.append((c+2*b+fixture)%6)
 elif a==5:debt=(sum(v)+fixture)%4;fixture=(fixture+1)%4
 history=history+(a,)
 if a==5:locked=(tuple(v),fixture,debt)
 return tuple(v),fixture,debt,history,locked
for x in LEVELS:
 s=((),0,0,(),None)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 t=advance(s,5);x["plan"]=x["seq"]+(5,);x["target"]=t
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SHOP
  for i in range(4):x=7+i*14;f[8:28,x:x+10]=FIXTURE;f[13:23,x+3:x+7]=TOOL if i==g.fixture else RELAY
  for i,v in enumerate(g.stack[-6:]):x=8+i*8;f[33:40,x:x+6]=GROUP;f[41:44,x:x+2+v]=TOOL
  for i,a in enumerate(g.history[-7:]):f[47:51,8+i*7:13+i*7]=DEBT if a==5 else RELAY
  f[54:58,8:8+g.debt*12+8]=DEBT
  if g.locked:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q620(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q620",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.stack=();self.fixture=self.debt=0;self.history=();self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.stack,self.fixture,self.debt,self.history,self.locked),a)
   if s is None:self.bad=True;self.lose()
   else:self.stack,self.fixture,self.debt,self.history,self.locked=s
  elif a==6:
   if (self.stack,self.fixture,self.debt,self.history,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
