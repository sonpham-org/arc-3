"""q499 Monsoon Dependency -- reuse nested weather subgoals at rare phase pairs."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,CLOUD,SEED,STORM,SUN,BUILT,PHASE,CURSOR,BAD=6,14,10,11,9,12,0,15,13,8
LEVELS=[
 {"name":"Rain Seed","periods":(2,3),"nodes":(((),(1,0,0),(1,1)),),"order":(0,)},
 {"name":"Delayed Cell","periods":(3,4),"nodes":(((),(1,0,0),(1,1)),((0,),(0,1,0),(0,3))),"order":(0,1)},
 {"name":"Shared Shower","periods":(3,5),"nodes":(((),(1,0,0),(1,1)),((0,),(0,1,0),(0,3)),((0,1),(0,0,1),(1,4))),"order":(0,1,2)},
 {"name":"Branching Storm","periods":(4,5),"nodes":(((),(1,0,0),(1,1)),((0,),(0,1,0),(3,3)),((0,),(0,0,1),(2,2)),((1,2),(1,1,0),(0,4))),"order":(0,2,1,3)},
 {"name":"Unequal Cycles","periods":(4,7),"nodes":(((),(1,0,0),(1,1)),((0,),(0,1,0),(3,3)),((0,),(0,0,1),(1,5)),((1,2),(1,0,1),(3,0))),"order":(0,1,2,3)},
 {"name":"Monsoon Dependency","periods":(5,7),"nodes":(((),(1,0,0),(1,1)),((0,),(0,1,0),(0,5)),((0,),(0,0,1),(3,3)),((1,2),(1,1,0),(2,0)),((2,3),(1,0,1),(4,2))),"order":(0,2,1,3,4)}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=GARDEN
  for i in range(len(x["nodes"])):
   px=7+i*10;f[10+i*6:15+i*6,px:px+8]=BUILT if i in g.built else CLOUD
  cols=(SEED,STORM,SUN)
  for i,n in enumerate(g.resources):f[45+i*4:48+i*4,8:11]=cols[i];f[45+i*4:48+i*4,13:13+n*9]=cols[i]
  f[57:60,7:7+g.phases[0]*7]=PHASE;f[60:63,7:7+g.phases[1]*6]=PHASE
  f[6:9,7+g.cursor*10:15+g.cursor*10]=CURSOR
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q499(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.built=set();self.cursor=0;self.resources=(0,0,0);self.phases=(0,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q499",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.built=set();self.cursor=0;self.resources=(0,0,0);self.phases=(0,0);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index];n=len(x["nodes"])
  if a==0:self.complete_action();return
  if a in (1,2,3):
   r=list(self.resources);r[a-1]+=1;self.resources=tuple(r)
  elif a==4:self.phases=((self.phases[0]+1)%x["periods"][0],(self.phases[1]+1)%x["periods"][1])
  elif a==5:self.cursor=(self.cursor+1)%n
  elif a==6:
   parents,need,window=x["nodes"][self.cursor]
   if self.cursor not in self.built and set(parents).issubset(self.built) and self.resources==need and self.phases==window:
    self.built.add(self.cursor);self.resources=(0,0,0)
    if len(self.built)==n:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
