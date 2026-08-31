"""q756 Backstage Obligation -- repay signed pressure debts to causal mask identities."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,PANE0,PANE1,POSITIVE,NEGATIVE,DEBT,REPAID,BAD=7,13,10,14,11,9,6,12,15
LEVELS=[
 {"name":"First Favor","borrows":(1,),"swaps":0},{"name":"Opposed Favor","borrows":(1,2),"swaps":0},
 {"name":"Mask Swap","borrows":(1,2),"swaps":1},{"name":"Repeated Pressure","borrows":(1,1,2),"swaps":2},
 {"name":"Long Obligation","borrows":(1,2,2,1),"swaps":3},{"name":"Backstage Obligation","borrows":(1,1,2,2,1),"swaps":4}]
def plan_for(x):
 slots=[0,1];debt=[0,0]
 for a in x["borrows"]:debt[slots[0] if a==1 else slots[1]]+=2 if a==1 else -1
 for _ in range(x["swaps"]):slots.reverse()
 return x["borrows"]+(3,)*x["swaps"]+tuple(4+slots.index(i) for i in range(2) if debt[i])
for x in LEVELS:x["plan"]=plan_for(x)
def advance(s,a,x):
 slots,debts,value,reward,repaid=s;slots=list(slots);debts=list(debts);repaid=list(repaid)
 if a==1:who=slots[0];debts[who]+=2;value+=2;reward+=1
 elif a==2:who=slots[1];debts[who]-=1;value-=1;reward+=1
 elif a==3:slots.reverse();reward+=1
 elif a in (4,5):
  who=slots[a-4]
  if not debts[who]:return None
  value-=debts[who];debts[who]=0;repaid.append(who)
 return tuple(slots),tuple(debts),value,reward,tuple(repaid)
def target(x):
 s=((0,1),(0,0),0,0,())
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STAGE;f[8:34,8:29]=PANE0;f[8:34,35:56]=PANE1
  for pos,who in enumerate(g.slots):x=11+pos*27;f[12:29,x:x+15]=PANE0+who*4
  width=min(abs(g.value),10)*4;f[39:43,8:8+width]=POSITIVE if g.value>=0 else NEGATIVE;f[47:51,8:28]=DEBT
  if g.repaid:f[54:59,39:56]=REPAID
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q756(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q756",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.slots=(0,1);self.debts=(0,0);self.value=self.reward=0;self.repaid=()
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.slots,self.debts,self.value,self.reward,self.repaid),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.slots,self.debts,self.value,self.reward,self.repaid=s
  elif a==6:
   if (self.slots,self.debts,self.value,self.reward,self.repaid)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
