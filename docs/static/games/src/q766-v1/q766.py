"""q766 Crossing Obligation -- repay identity debt using marked, disjoint controller views."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,PASS0,PASS1,DEBT,CARGO,DOCK,MARK0,MARK1,GOAL,BAD=9,5,11,14,10,12,6,7,4,13,15
LEVELS=[
 {"name":"First Fare","seq":(1,5)},{"name":"Swapped Passenger","seq":(1,2,1,5)},
 {"name":"Marked Debt","seq":(1,4,3,1,5)},{"name":"Two Views","seq":(1,4,3,1,2,5)},
 {"name":"Alternating Obligation","seq":(1,4,3,1,5,4,3,5)},
 {"name":"Crossing Obligation","seq":(1,2,4,3,1,4,3,2,5,2,1,5)}]
def advance(s,a):
 ids,debts,cargo,controller,marks,order=s;ids=list(ids);debts=list(debts);cargo=list(cargo)
 if a==1:i=ids[controller];debts[i]+=1;cargo[i]+=3
 elif a==2:ids.reverse()
 elif a==3:
  if not marks or marks[-1][0]!=controller:return None
  controller^=1
 elif a==4:marks=marks+((controller,ids[controller],debts[ids[controller]],cargo[ids[controller]]),)
 elif a==5:
  i=ids[controller]
  if debts[i]==0:return None
  cargo[i]-=debts[i];debts[i]=0;order=order+(i,)
 return tuple(ids),tuple(debts),tuple(cargo),controller,marks,order
for x in LEVELS:
 s=((0,1),(0,0),(0,0),0,(),())
 for a in x["seq"]:s=advance(s,a);assert s is not None
 x["plan"]=x["seq"]
def target(x):
 s=((0,1),(0,0),(0,0),0,(),())
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER;cols=(PASS0,PASS1)
  for slot,i in enumerate(g.ids):
   y=8+slot*21;f[y:y+15,8:35]=cols[i];f[y:y+5,40:40+min(g.cargo[i],7)*2]=CARGO;f[y+9:y+14,40:40+min(g.debts[i],5)*3]=DEBT
  f[47:50,8:56]=DOCK
  for i,m in enumerate(g.marks[-4:]):f[51:55,8+i*11:16+i*11]=MARK0 if m[0]==0 else MARK1
  if tuple(g.debts)==(0,0) and any(g.cargo):f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q766(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q766",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.ids=(0,1);self.debts=(0,0);self.cargo=(0,0);self.controller=0;self.marks=();self.order=()
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.ids,self.debts,self.cargo,self.controller,self.marks,self.order),a)
   if s is None:self.bad=True;self.lose()
   else:self.ids,self.debts,self.cargo,self.controller,self.marks,self.order=s
  elif a==6:
   if (self.ids,self.debts,self.cargo,self.controller,self.marks,self.order)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
