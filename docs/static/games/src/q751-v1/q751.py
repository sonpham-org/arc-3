"""q751 Tapestry Obligation -- repay shuttle debt after pattern completion rewires adjacency."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LOOM,SHUTTLE,THREAD,IDENTITY,REWIRE,DEBT,GOAL,BAD=8,0,14,10,6,11,9,13,15
LEVELS=[{"name":"Borrowed Thread","seq":(4,)},{"name":"Moved Creditor","seq":(4,1)},{"name":"Pattern Debt","seq":(4,2,1)},{"name":"Rewired Return","seq":(4,1,3,2)},{"name":"Identity Loom","seq":(4,2,1,3,2,1)},{"name":"Tapestry Obligation","seq":(4,1,2,3,1,2,3,1,2)}]
def advance(s,a):
 identities,threads,graph,creditor,debt,repaid=s;i=list(identities);t=list(threads)
 if a==1:i[0],i[1]=i[1],i[0];t[0],t[1]=t[1],t[0]
 elif a==2:i=i[1:]+i[:1];t=t[-1:]+t[:-1];graph=(graph+1)%4
 elif a==3:graph=(graph+1+sum(t)%2)%4;t=[(v+graph)%6 for v in t]
 elif a==4:creditor=i[1];debt=(t[1]+graph+1)%6
 elif a==5:repaid=(i.index(creditor),tuple(t),graph,debt) if creditor>=0 else None
 return tuple(i),tuple(t),graph,creditor,debt,repaid
for x in LEVELS:
 s=((0,1,2),(0,2,4),0,-1,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LOOM
  for slot,(identity,thread) in enumerate(zip(g.identities,g.threads)):
   x=8+slot*17;f[9:31,x:x+13]=THREAD;f[13+thread*2:19+thread*2,x+3:x+10]=SHUTTLE;f[33+identity:36+identity,x:x+13]=IDENTITY
  f[42:46,8:8+g.graph*11+7]=REWIRE;f[50:54,8:8+g.debt*8+5]=DEBT
  if g.repaid:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q751(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q751",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.identities=(0,1,2);self.threads=(0,2,4);self.graph=0;self.creditor=-1;self.debt=0;self.repaid=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.identities,self.threads,self.graph,self.creditor,self.debt,self.repaid=advance((self.identities,self.threads,self.graph,self.creditor,self.debt,self.repaid),a)
  elif a==6:
   if (self.identities,self.threads,self.graph,self.creditor,self.debt,self.repaid)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
