"""a107 Nesting Cargo -- change effective items through hierarchical containment."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,HOLD,CRATE_A,CRATE_B,CRATE_C,NEST,WEIGHT,BALANCE,SPACE,BAD=3,8,12,14,10,11,4,13,6,15
LEVELS=[
 {"name":"Nest Cargo","seq":(1,)},{"name":"Select Piece","seq":(2,)},
 {"name":"Place Group","seq":(3,1)},{"name":"Balance Hold","seq":(1,2,3,4,2)},
 {"name":"Hierarchical Pack","seq":(1,2,1,3,2,4,3)},{"name":"Nesting Cargo","seq":(1,2,3,1,4,2,1,3,4,2)},
]
def advance(s,a):
 parents,positions,cursor,space,balance,nests,history,snapshot=s;pa=list(parents);p=list(positions)
 if a==1:
  other=(cursor+1)%4;pa[cursor]=-1 if pa[cursor]==other else other;nests=(nests+1)%7;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%4;history=(history+(2,))[-8:]
 elif a==3:p[cursor]=(p[cursor]+1)%6;history=(history+(3,))[-8:]
 elif a==4:
  roots=[i for i,x in enumerate(pa) if x<0];space=sum(1+(i%3) for i in roots);balance=sum((p[i]-3)*(i+1) for i in roots);history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(pa),tuple(p),cursor,space,balance,nests,history)
 return tuple(pa),tuple(p),cursor,space,balance,nests,history,snapshot
for x in LEVELS:
 s=((-1,-1,-1,-1),(0,1,3,5),0,10,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HOLD;cols=(CRATE_A,CRATE_B,CRATE_C,WEIGHT)
  for i,(parent,pos) in enumerate(zip(g.parents,g.positions)):
   x=8+pos*8;y=38-(i%2)*14;f[y:y+13,x:x+11]=cols[i]
   if parent>=0:f[y+3:y+10,x+3:x+8]=NEST
   if i==g.cursor:f[y-4:y-1,x:x+11]=BALANCE
  f[8:12,8:8+min(10,g.space)*4]=SPACE;mid=32+max(-20,min(20,g.balance));f[54:58,min(32,mid):max(33,mid)]=BALANCE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A107(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a107",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.parents,self.positions,self.cursor,self.space,self.balance,self.nests,self.history,self.snapshot=((-1,-1,-1,-1),(0,1,3,5),0,10,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.parents,self.positions,self.cursor,self.space,self.balance,self.nests,self.history,self.snapshot=advance((self.parents,self.positions,self.cursor,self.space,self.balance,self.nests,self.history,self.snapshot),a)
  elif a==6:
   if (self.parents,self.positions,self.cursor,self.space,self.balance,self.nests,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
