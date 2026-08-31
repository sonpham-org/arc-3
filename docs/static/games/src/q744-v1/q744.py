"""q744 Honeycomb Obligation -- repay courier debt across local and colony clocks."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,APIARY,CELL,COURIER,IDENTITY,CLOCK,DEBT,GOAL,BAD=8,0,11,14,6,10,9,13,15
LEVELS=[
 {"name":"Borrowed Nectar","seq":(4,)},{"name":"Moved Courier","seq":(4,1)},
 {"name":"Local Clock","seq":(4,2,1)},{"name":"Colony Debt","seq":(4,1,3,2)},
 {"name":"Timed Return","seq":(4,2,1,3,2,1)},
 {"name":"Honeycomb Obligation","seq":(4,1,2,3,1,2,3,1,2)}]
def advance(s,a):
 identities,nectar,local,outer,creditor,debt,repaid=s;i=list(identities);n=list(nectar)
 if a==1:i[0],i[1]=i[1],i[0];n[0],n[1]=n[1],n[0];local=(local+1)%3
 elif a==2:i=i[1:]+i[:1];n=n[-1:]+n[:-1];local=(local+2)%3
 elif a==3:outer=(outer+1+int(local==0))%4;n=[(v+outer)%6 for v in n]
 elif a==4:creditor=i[1];debt=(n[1]+local+outer+1)%6
 elif a==5:repaid=(i.index(creditor),tuple(n),local,outer,debt) if creditor>=0 else None
 if a in (1,2) and local==0:outer=(outer+1)%4
 return tuple(i),tuple(n),local,outer,creditor,debt,repaid
for x in LEVELS:
 s=((0,1,2),(0,2,4),0,0,-1,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=APIARY
  for slot,(identity,nectar) in enumerate(zip(g.identities,g.nectar)):
   x=8+slot*17;f[9:31,x:x+13]=CELL;f[13+nectar*2:19+nectar*2,x+3:x+10]=COURIER;f[33+identity:36+identity,x:x+13]=IDENTITY
  f[41:45,8:8+g.local*15+10]=CLOCK;f[47:51,8:8+g.outer*11+7]=CELL;f[53:57,8:8+g.debt*8+5]=DEBT
  if g.repaid:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q744(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q744",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.identities=(0,1,2);self.nectar=(0,2,4);self.local=self.outer=0;self.creditor=-1;self.debt=0;self.repaid=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.identities,self.nectar,self.local,self.outer,self.creditor,self.debt,self.repaid=advance((self.identities,self.nectar,self.local,self.outer,self.creditor,self.debt,self.repaid),a)
  elif a==6:
   if (self.identities,self.nectar,self.local,self.outer,self.creditor,self.debt,self.repaid)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
