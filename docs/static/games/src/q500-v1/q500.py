"""q500 Workbench Dependency -- build shared prerequisites while repaying helper identity debt."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SHOP,FIXTURE,TOOL,BUILT,HELPER,DEBT,CURSOR,BAD=7,0,3,10,14,12,13,9,8
LEVELS=[
 {"name":"First Fixture","nodes":(((),(1,0,0),0,False,-1),),"order":(0,)},
 {"name":"Borrowed Tool","nodes":(((),(1,0,0),0,True,-1),((0,),(0,1,0),1,False,0)),"order":(0,1)},
 {"name":"Shared Subgoal","nodes":(((),(1,0,0),0,True,-1),((0,),(0,1,0),1,False,-1),((0,1),(0,0,1),2,False,0)),"order":(0,1,2)},
 {"name":"Branching Bench","nodes":(((),(1,0,0),1,True,-1),((0,),(0,1,0),2,False,1),((0,),(0,0,1),0,True,-1),((1,2),(1,1,0),1,False,0)),"order":(0,2,1,3)},
 {"name":"Identity Obligation","nodes":(((),(1,0,0),2,True,-1),((0,),(0,1,0),0,False,2),((0,),(0,0,1),1,True,-1),((1,2),(1,0,1),2,False,1)),"order":(0,1,2,3)},
 {"name":"Workbench Dependency","nodes":(((),(1,0,0),0,True,-1),((0,),(0,1,0),2,False,-1),((0,),(0,0,1),1,True,-1),((1,2),(1,1,0),0,False,0),((2,3),(1,0,1),2,False,1)),"order":(0,2,1,3,4)}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=SHOP
  for i in range(len(x["nodes"])):px=7+i*10;f[10+i*6:15+i*6,px:px+8]=BUILT if i in g.built else FIXTURE
  for i,n in enumerate(g.resources):f[44+i*4:47+i*4,8:11]=TOOL+i;f[44+i*4:47+i*4,13:13+n*8]=TOOL+i
  f[7:10,7+g.cursor*10:15+g.cursor*10]=CURSOR;f[56:59,8:8+g.helper*15]=HELPER
  for i,h in enumerate(sorted(g.debts)):f[59:62,8+i*12:18+i*12]=DEBT
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q500(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.built=set();self.cursor=0;self.resources=(0,0,0);self.helper=0;self.debts=set();self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q500",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.built=set();self.cursor=0;self.resources=(0,0,0);self.helper=0;self.debts=set();self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index];n=len(x["nodes"])
  if a==0:self.complete_action();return
  if a in (1,2,3):r=list(self.resources);r[a-1]+=1;self.resources=tuple(r)
  elif a==4:self.helper=(self.helper+1)%3
  elif a==5:self.cursor=(self.cursor+1)%n
  elif a==6:
   parents,need,helper,borrow,repay=x["nodes"][self.cursor]
   ok=self.cursor not in self.built and set(parents).issubset(self.built) and self.resources==need and self.helper==helper and (repay<0 or repay in self.debts)
   if ok:
    self.built.add(self.cursor);self.resources=(0,0,0)
    if repay>=0:self.debts.remove(repay)
    if borrow:self.debts.add(helper)
    if len(self.built)==n and not self.debts:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
