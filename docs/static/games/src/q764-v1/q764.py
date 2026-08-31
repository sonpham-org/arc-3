"""q764 Tessera Obligation -- repay identity-bound mosaic debt at a macro interruption window."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MOSAIC,TILE,SEAM,IDENTITY,DEBT,WINDOW,GOAL,BAD=5,10,14,8,6,12,11,13,15
LEVELS=[{"name":"Borrowed Tessera","seq":(1,)},{"name":"Seam Exchange","seq":(2,1)},{"name":"Identity Mark","seq":(3,1,2)},{"name":"Macro Window","seq":(4,2,1,3)},{"name":"Delayed Repayment","seq":(2,3,1,4,2,1)},{"name":"Tessera Obligation","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 identities,positions,debt,seam,phase,history,settled=s;ids=list(identities);pos=list(positions);d=list(debt)
 if a==1:borrower=ids[seam%3];d[borrower]+=1;pos[borrower]=(pos[borrower]+1+phase)%6;history=history+((borrower,1,seam),)
 elif a==2:ids[0],ids[2]=ids[2],ids[0];pos[0],pos[2]=pos[2],pos[0];seam=(seam+1)%4
 elif a==3:creditor=ids[(seam+1)%3];d[creditor]=max(0,d[creditor]-1);history=history+((creditor,-1,seam),)
 elif a==4:phase=(phase+1)%5;seam=(seam+int(phase==3))%4
 elif a==5:settled=(tuple(ids),tuple(pos),tuple(d),seam,phase,history[-5:])
 return tuple(ids),tuple(pos),tuple(d),seam,phase,history,settled
for x in LEVELS:
 s=((0,1,2),(0,2,4),(0,0,0),0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MOSAIC
  for lane,i in enumerate(g.identities):x=8+g.positions[i]*8;y=8+lane*9;f[y:y+7,7:57]=SEAM;f[y:y+7,x:x+7]=TILE;f[y+2:y+5,x+2:x+5]=IDENTITY
  for i,d in enumerate(g.debt):x=9+i*17;f[36:42,x:x+12]=DEBT;f[43:46,x:x+2+d*3]=IDENTITY
  f[50:54,8:8+g.seam*11+8]=SEAM;f[56:60,8:8+g.phase*9+7]=WINDOW
  if g.settled:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q764(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q764",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.identities=(0,1,2);self.positions=(0,2,4);self.debt=(0,0,0);self.seam=self.phase=0;self.history=();self.settled=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.identities,self.positions,self.debt,self.seam,self.phase,self.history,self.settled=advance((self.identities,self.positions,self.debt,self.seam,self.phase,self.history,self.settled),a)
  elif a==6:
   if (self.identities,self.positions,self.debt,self.seam,self.phase,self.history,self.settled)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
