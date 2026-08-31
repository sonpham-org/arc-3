"""q761 Pollen Obligation -- repay causal identity after a wear-driven appearance exchange."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,PANE0,PANE1,DEBT,REWARD,WEAR,REPAID,BAD=7,14,11,9,13,12,8,10,15
LEVELS=[
 {"name":"First Favor","wear":1,"manual":0},{"name":"Visible Exchange","wear":2,"manual":0},
 {"name":"Double Exchange","wear":2,"manual":1},{"name":"Delayed Debt","wear":3,"manual":1},
 {"name":"Long Favor","wear":4,"manual":2},{"name":"Pollen Obligation","wear":5,"manual":3}]
for x in LEVELS:
 slots=[0,1];slots.reverse()
 for _ in range(x["manual"]):slots.reverse()
 choice=slots.index(0);x["plan"]=(1,)+(2,)*x["wear"]+(3,)*x["manual"]+(4+choice,)
def advance(s,a,x):
 slots,debtor,reward,wear,repaid=s;slots=list(slots)
 if a==1:
  if debtor is not None:return None
  debtor=slots[0];reward+=2
 elif a==2:
  reward+=1;wear+=1
  if wear==x["wear"]:slots.reverse()
 elif a==3:slots.reverse()
 elif a in (4,5):
  idx=a-4
  if debtor is None or slots[idx]!=debtor:return None
  reward-=1;repaid=debtor
 return tuple(slots),debtor,reward,wear,repaid
def target(x):
 s=((0,1),None,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MEADOW;f[8:34,8:29]=PANE0;f[8:34,35:56]=PANE1
  for pos,who in enumerate(g.slots):x=11+pos*27;f[12:29,x:x+15]=PANE0+who*2
  f[39:43,8:8+g.reward*5]=REWARD;f[47:51,8:8+min(g.wear,6)*8]=WEAR
  if g.debtor is not None:f[54:58,8:28]=DEBT+g.debtor
  if g.repaid is not None:f[54:59,39:56]=REPAID
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q761(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q761",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.slots=(0,1);self.debtor=self.repaid=None;self.reward=self.wear=0
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.slots,self.debtor,self.reward,self.wear,self.repaid),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.slots,self.debtor,self.reward,self.wear,self.repaid=s
  elif a==6:
   if (self.slots,self.debtor,self.reward,self.wear,self.repaid)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
