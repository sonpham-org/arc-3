"""q469 Monsoon Lineage -- preserve rain-seed ancestry to a sparse unequal-cycle window."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,CLOUD,SEED,TRAIL,PHASE,SELECT,TARGET,BAD=6,14,10,11,15,12,9,0,8
LEVELS=[{"name":"First Seed","periods":(2,3),"window":(1,1),"ancestor":1,"ops":(1,)},{"name":"Delayed Cell","periods":(3,4),"window":(2,2),"ancestor":2,"ops":(3,1)},{"name":"Merged Shower","periods":(3,5),"window":(0,3),"ancestor":3,"ops":(1,2,3)},{"name":"Unequal Storm","periods":(4,5),"window":(0,4),"ancestor":2,"ops":(3,1,2,1)},{"name":"Sparse Monsoon","periods":(4,7),"window":(1,5),"ancestor":1,"ops":(1,3,2,1,3)},{"name":"Monsoon Lineage","periods":(5,7),"window":(4,2),"ancestor":3,"ops":(3,1,2,3,1,2)}]
def evolve(tokens,a):
 t=[list(x) for x in tokens]
 if a==1:
  m,c=t.pop(0);t.extend([[m,(c+1)%4],[m,(c+2)%4]])
 elif a==2 and len(t)>=2:
  p=t.pop(0);q=t.pop(0);t.insert(0,[p[0]|q[0],(p[1]+q[1])%4])
 elif a==3:
  colors=[x[1] for x in t][1:]+[t[0][1]]
  for x,c in zip(t,colors):x[1]=c
 return tuple((x[0],x[1]) for x in t)
def target(x):
 t=((1,0),(2,1),(4,2))
 for a in x["ops"]:t=evolve(t,a)
 return t
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=GARDEN
  for i,(mask,color) in enumerate(g.tokens):px=7+i*12;f[12:21,px:px+9]=CLOUD;f[24:30,px:px+9]=SEED+color%3;f[32:35,px:px+min(mask,7)*2]=TRAIL
  f[43:46,8:8+g.phases[0]*8]=PHASE;f[48:51,8:8+g.phases[1]*6]=PHASE;f[54:57,8:8+g.selection*13]=SELECT;f[58:60,8:8+x["ancestor"]*13]=TARGET
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q469(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.tokens=((1,0),(2,1),(4,2));self.phases=(0,0);self.selection=0;self.bad=False;self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q469",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.tokens=((1,0),(2,1),(4,2));self.phases=(0,0);self.selection=0;self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.tokens=evolve(self.tokens,a)
  elif a==4:self.phases=((self.phases[0]+1)%x["periods"][0],(self.phases[1]+1)%x["periods"][1])
  elif a==5:self.selection=(self.selection+1)%4
  elif a==6:
   if self.tokens==self.target and self.phases==x["window"] and self.selection==x["ancestor"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
