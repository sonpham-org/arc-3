"""q754 Moraine Obligation -- repay identity-bound raft debt into an outer completion order."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ICE,RAFT0,RAFT1,RAFT2,DEBT,CARGO,ROTATE,OUTER,GOAL,BAD=9,5,11,14,12,10,6,7,4,13,15
LEVELS=[
 {"name":"First Debt","seq":(1,5)},{"name":"Full Drift","seq":(1,2,2,2,5)},
 {"name":"Two Rafts","seq":(1,2,1,5,2,2,5)},{"name":"Reversed Crevasse","seq":(1,3,2,1,5,2,2,5)},
 {"name":"Outer Obligation","seq":(1,2,1,2,1,5,2,5,2,5)},
 {"name":"Moraine Obligation","seq":(1,3,2,1,4,5,2,2,5)}]
def advance(s,a):
 ids,debts,cargo,direction,outer,order=s;ids=list(ids);debts=list(debts);cargo=list(cargo);outer=list(outer)
 if a==1:i=ids[0];debts[i]+=1;cargo[i]+=3
 elif a==2:ids=ids[1:]+ids[:1] if direction>0 else ids[-1:]+ids[:-1]
 elif a==3:direction*=-1
 elif a==4:outer[ids[0]]=(outer[ids[0]]+1)%4
 elif a==5:
  i=ids[0]
  if debts[i]==0:return None
  cargo[i]-=debts[i];outer[i]=(cargo[i]+1)%4;debts[i]=0;order=order+(i,)
 return tuple(ids),tuple(debts),tuple(cargo),direction,tuple(outer),order
for x in LEVELS:
 s=((0,1,2),(0,0,0),(0,0,0),1,(0,0,0),())
 for a in x["seq"]:s=advance(s,a);assert s is not None
 x["plan"]=x["seq"]
def target(x):
 s=((0,1,2),(0,0,0),(0,0,0),1,(0,0,0),())
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ICE;cols=(RAFT0,RAFT1,RAFT2)
  for slot,i in enumerate(g.ids):
   x=7+slot*18;f[9:29,x:x+14]=cols[i];f[32:36,x:x+min(g.cargo[i],7)*2]=CARGO;f[39:43,x:x+min(g.debts[i],5)*3]=DEBT
  for i,v in enumerate(g.outer):f[47:51,8+i*16:8+i*16+v*3+4]=OUTER
  for i,v in enumerate(g.order[-4:]):f[54:58,8+i*10:15+i*10]=cols[v]
  if tuple(g.debts)==(0,0,0) and any(g.cargo):f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q754(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q754",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.ids=(0,1,2);self.debts=(0,0,0);self.cargo=(0,0,0);self.direction=1;self.outer=(0,0,0);self.order=()
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.ids,self.debts,self.cargo,self.direction,self.outer,self.order),a)
   if s is None:self.bad=True;self.lose()
   else:self.ids,self.debts,self.cargo,self.direction,self.outer,self.order=s
  elif a==6:
   if (self.ids,self.debts,self.cargo,self.direction,self.outer,self.order)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
