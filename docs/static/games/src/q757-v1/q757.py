"""q757 Catalyst Obligation -- remember a helper before hidden borrowing and later appearance swaps."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,REFINERY,PANE0,PANE1,MEMORY,DEBT,REWARD,REPAID,BAD=7,12,9,14,6,13,11,10,15
LEVELS=[
 {"name":"First Helper","swaps":0},{"name":"Visible Swap","swaps":1},{"name":"Double Swap","swaps":2},
 {"name":"Delayed Obligation","swaps":3},{"name":"Long Credit","swaps":4},{"name":"Catalyst Obligation","swaps":5}]
for x in LEVELS:
 slots=[0,1]
 for _ in range(x["swaps"]):slots.reverse()
 x["plan"]=(1,2)+(3,)*x["swaps"]+(4+slots.index(0),)
def advance(s,a,x):
 slots,memory,visible,debtor,reward,repaid=s;slots=list(slots)
 if a==1:memory=slots[0];visible=1
 elif a==2:
  if memory is None or debtor is not None:return None
  visible=0;debtor=memory;reward+=2
 elif a==3:slots.reverse();reward+=1
 elif a in (4,5):
  idx=a-4
  if debtor is None or memory!=debtor or slots[idx]!=debtor:return None
  reward-=1;repaid=debtor
 return tuple(slots),memory,visible,debtor,reward,repaid
def target(x):
 s=((0,1),None,1,None,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=REFINERY;f[8:34,8:29]=PANE0;f[8:34,35:56]=PANE1
  for pos,who in enumerate(g.slots):x=11+pos*27;f[12:29,x:x+15]=PANE0+who*5
  f[39:43,8:28]=MEMORY;f[39:43,36:56]=DEBT;f[47:51,8:8+g.reward*6]=REWARD
  if g.repaid is not None:f[54:59,39:56]=REPAID
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q757(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q757",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.slots=(0,1);self.memory=self.debtor=self.repaid=None;self.visible=1;self.reward=0
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.slots,self.memory,self.visible,self.debtor,self.reward,self.repaid),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.slots,self.memory,self.visible,self.debtor,self.reward,self.repaid=s
  elif a==6:
   if (self.slots,self.memory,self.visible,self.debtor,self.reward,self.repaid)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
