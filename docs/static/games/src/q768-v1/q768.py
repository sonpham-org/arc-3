"""q768 Escapement Obligation -- repay identity-bound weight debt after diagnostic interventions."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TOWER,GEAR,WEIGHT,IDENTITY,PROBE,DEBT,GOAL,BAD=8,0,12,14,6,11,9,13,15
LEVELS=[
 {"name":"Borrowed Weight","seq":(4,)},{"name":"Moved Creditor","seq":(4,1)},
 {"name":"Fault Probe","seq":(4,2,1)},{"name":"Diagnostic Debt","seq":(4,1,3,2)},
 {"name":"Identity Intervention","seq":(4,2,1,3,2,1)},
 {"name":"Escapement Obligation","seq":(4,1,2,3,1,2,3,1,2)}]
def advance(s,a):
 identities,weights,fault,probes,creditor,debt,repaid=s;i=list(identities);w=list(weights)
 if a==1:i[0],i[1]=i[1],i[0];w[0],w[1]=w[1],w[0]
 elif a==2:i=i[1:]+i[:1];w=w[-1:]+w[:-1];probes=probes+((i[0],fault),)
 elif a==3:fault=(fault+1+sum(w))%4;w=[(x+fault)%6 for x in w]
 elif a==4:creditor=i[1];debt=(w[1]+fault+1)%6
 elif a==5:repaid=(i.index(creditor),tuple(w),fault,probes[-3:],debt) if creditor>=0 else None
 return tuple(i),tuple(w),fault,probes,creditor,debt,repaid
for x in LEVELS:
 s=((0,1,2),(0,2,4),0,(),-1,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TOWER
  for slot,(identity,weight) in enumerate(zip(g.identities,g.weights)):
   x=8+slot*17;f[9:31,x:x+13]=GEAR;f[13+weight*2:19+weight*2,x+3:x+10]=WEIGHT;f[33+identity:36+identity,x:x+13]=IDENTITY
  for j,p in enumerate(g.probes[-2:]):x=9+j*22;f[41:47,x:x+15]=PROBE;f[43:45,x+3:x+5+p[1]*2]=GEAR
  f[51:55,8:8+g.debt*8+5]=DEBT
  if g.creditor>=0:f[56:60,8:8+g.identities.index(g.creditor)*17+13]=DEBT
  if g.repaid:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q768(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q768",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.identities=(0,1,2);self.weights=(0,2,4);self.fault=0;self.probes=();self.creditor=-1;self.debt=0;self.repaid=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.identities,self.weights,self.fault,self.probes,self.creditor,self.debt,self.repaid=advance((self.identities,self.weights,self.fault,self.probes,self.creditor,self.debt,self.repaid),a)
  elif a==6:
   if (self.identities,self.weights,self.fault,self.probes,self.creditor,self.debt,self.repaid)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
