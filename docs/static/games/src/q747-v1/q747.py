"""q747 Canopy Obligation -- repay a seed identity through a capacity-one orchard store."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,SEED,SHADE,IDENTITY,STORE,DEBT,GOAL,BAD=8,0,14,10,6,11,9,13,15
LEVELS=[
 {"name":"Borrowed Seed","seq":(4,)},{"name":"Moved Creditor","seq":(4,1)},
 {"name":"Narrow Store","seq":(4,2,1)},{"name":"Seasonal Shade","seq":(4,1,3,2)},
 {"name":"Ordered Return","seq":(4,2,1,3,2,1)},
 {"name":"Canopy Obligation","seq":(4,1,2,3,1,2,3,1,2)}]
def advance(s,a):
 identities,zones,shade,store,creditor,debt,repaid=s;i=list(identities);z=list(zones)
 if a==1:i[0],i[1]=i[1],i[0];z[0],z[1]=z[1],z[0]
 elif a==2:
  if store<0:store=i[1];i[1]=-1;z[1]=(z[1]+1+shade)%4
  else:i[2],store=store,-1;z[2]=(z[2]+2)%4
 elif a==3:shade=(shade+1)%3;z=[(v+shade)%4 for v in z]
 elif a==4:creditor=i[0];debt=(z[0]+shade+1)%4
 elif a==5:repaid=((i.index(creditor) if creditor in i else 3),tuple(z),shade,store,debt) if creditor>=0 else None
 return tuple(i),tuple(z),shade,store,creditor,debt,repaid
for x in LEVELS:
 s=((0,1,2),(0,1,2),0,-1,-1,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ORCHARD
  for slot,(identity,zone) in enumerate(zip(g.identities,g.zones)):
   x=8+slot*17;f[9:31,x:x+13]=SHADE;f[24-zone*4:29,x+3:x+10]=SEED;f[33+identity:36+identity,x:x+13]=IDENTITY
  f[41:48,8:22]=STORE if g.store>=0 else SHADE;f[43:46,27:55]=DEBT
  f[51:55,8:8+g.shade*15+10]=SHADE
  if g.creditor>=0:
   slot=g.identities.index(g.creditor) if g.creditor in g.identities else 3;f[56:60,8:8+slot*13+10]=DEBT
  if g.repaid:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q747(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q747",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.identities=(0,1,2);self.zones=(0,1,2);self.shade=0;self.store=-1;self.creditor=-1;self.debt=0;self.repaid=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.identities,self.zones,self.shade,self.store,self.creditor,self.debt,self.repaid=advance((self.identities,self.zones,self.shade,self.store,self.creditor,self.debt,self.repaid),a)
  elif a==6:
   if (self.identities,self.zones,self.shade,self.store,self.creditor,self.debt,self.repaid)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
