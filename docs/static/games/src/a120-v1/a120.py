"""a120 Chain Exchange -- clear cyclic desires that bilateral trades cannot unlock."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,RING,AGENT,OBJECT_A,OBJECT_B,OBJECT_C,DESIRE,CYCLE,SATISFIED,BLOCKED=1,8,9,12,14,10,11,13,4,6
BAD=15
DESIRES=(1,2,0,4,5,3)
LEVELS=[
 {"name":"Change Holding","seq":(1,)},{"name":"Select Agent","seq":(2,)},
 {"name":"Commit Cycle","seq":(3,1)},{"name":"Reject Bilateral","seq":(1,2,3,4,2)},
 {"name":"Clear One Ring","seq":(1,3,2,1,4,3,2)},{"name":"Chain Exchange","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 holdings,cursor,commits,satisfied,blocked,history,snapshot=s;h=list(holdings)
 if a==1:h[cursor]=(h[cursor]+1)%6;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:
  group=(0,1,2) if cursor<3 else (3,4,5);tmp=h[group[-1]]
  for i in range(len(group)-1,0,-1):h[group[i]]=h[group[i-1]]
  h[group[0]]=tmp;commits=(commits+1)%5;history=(history+(3,))[-8:]
 elif a==4:
  satisfied=sum(int(h[i]==DESIRES[i]) for i in range(6));blocked=sum(int(h[i]!=DESIRES[i] and h[DESIRES[i]]!=i) for i in range(6));history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(h),cursor,commits,satisfied,blocked,history)
 return tuple(h),cursor,commits,satisfied,blocked,history,snapshot
for x in LEVELS:
 s=((0,1,2,3,4,5),0,0,0,6,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=RING;pts=((31,9),(49,20),(49,42),(31,53),(13,42),(13,20));cols=(OBJECT_A,OBJECT_B,OBJECT_C)
  for i,(x,y) in enumerate(pts):
   f[y-5:y+6,x-5:x+6]=AGENT;f[y-2:y+3,x-2:x+3]=cols[g.holdings[i]%3]
   tx,ty=pts[DESIRES[i]];f[min(y,ty):max(y+1,ty+1),min(x,tx):max(x+1,tx+1)]=DESIRE
   if i==g.cursor:f[y-8:y-6,x-6:x+7]=CYCLE
  f[55:59,8:8+g.satisfied*7]=SATISFIED;f[7:10,8:8+g.blocked*7]=BLOCKED
  if g.bad:f[1:4,18:46]=BAD
  return f
class A120(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a120",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.holdings,self.cursor,self.commits,self.satisfied,self.blocked,self.history,self.snapshot=((0,1,2,3,4,5),0,0,0,6,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.holdings,self.cursor,self.commits,self.satisfied,self.blocked,self.history,self.snapshot=advance((self.holdings,self.cursor,self.commits,self.satisfied,self.blocked,self.history,self.snapshot),a)
  elif a==6:
   if (self.holdings,self.cursor,self.commits,self.satisfied,self.blocked,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
