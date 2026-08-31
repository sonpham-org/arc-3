"""q762 Semaphore Obligation -- repay identity-bound signal debt after miniature policy tests."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,YARD,FLAG,BEAM,IDENTITY,TEST,DEBT,GOAL,BAD=8,0,14,10,6,11,9,13,15
LEVELS=[
 {"name":"Borrowed Flag","seq":(4,)},{"name":"Moved Creditor","seq":(4,1)},
 {"name":"First Testbed","seq":(4,2,1)},{"name":"Relay Debt","seq":(4,1,3,2)},
 {"name":"Policy Commitment","seq":(4,2,1,3,2,1)},
 {"name":"Semaphore Obligation","seq":(4,1,2,3,1,2,3,1,2)}]
def advance(s,a):
 identities,signals,tests,creditor,debt,repaid=s;i=list(identities);v=list(signals);t=list(tests)
 if a==1:i[0],i[1]=i[1],i[0];v[0],v[1]=v[1],v[0]
 elif a==2:i=i[1:]+i[:1];v=v[-1:]+v[:-1];t[0]=(t[0]+v[0])%4
 elif a==3:v=[(x+j+1)%6 for j,x in enumerate(v)];t[1]=(t[1]+sum(v))%4
 elif a==4:creditor=i[1];debt=(v[1]+sum(t)+1)%6
 elif a==5:repaid=(i.index(creditor),tuple(v),tuple(t),debt) if creditor>=0 else None
 return tuple(i),tuple(v),tuple(t),creditor,debt,repaid
for x in LEVELS:
 s=((0,1,2),(0,2,4),(0,0),-1,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=YARD
  for slot,(identity,signal) in enumerate(zip(g.identities,g.signals)):
   x=8+slot*17;f[9:31,x:x+13]=BEAM;f[13+signal*2:19+signal*2,x+3:x+10]=FLAG;f[33+identity:36+identity,x:x+13]=IDENTITY
  for j,v in enumerate(g.tests):x=9+j*22;f[41:47,x:x+15]=TEST;f[43:45,x+3:x+5+v*2]=FLAG
  f[51:55,8:8+g.debt*8+5]=DEBT
  if g.creditor>=0:f[56:60,8:8+g.identities.index(g.creditor)*17+13]=DEBT
  if g.repaid:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q762(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q762",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.identities=(0,1,2);self.signals=(0,2,4);self.tests=(0,0);self.creditor=-1;self.debt=0;self.repaid=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.identities,self.signals,self.tests,self.creditor,self.debt,self.repaid=advance((self.identities,self.signals,self.tests,self.creditor,self.debt,self.repaid),a)
  elif a==6:
   if (self.identities,self.signals,self.tests,self.creditor,self.debt,self.repaid)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
