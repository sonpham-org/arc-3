"""a117 Fair Split -- allocate indivisible tiles without envy under inferred values."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,TABLE,TILE_A,TILE_B,OWNER_A,OWNER_B,VALUE_A,VALUE_B,ENVY,NEED=14,8,12,10,9,13,4,11,6,7
BAD=15
VALUES_A=(4,1,3,1,5,2,4,2);VALUES_B=(1,4,2,5,1,4,2,3)
LEVELS=[
 {"name":"Move Tile","seq":(1,)},{"name":"Select Tile","seq":(2,)},
 {"name":"Reveal Values","seq":(3,1)},{"name":"Check Envy","seq":(1,2,3,4,2)},
 {"name":"Meet Both Needs","seq":(1,3,2,1,4,3,2)},{"name":"Fair Split","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 owners,cursor,view,utility_a,utility_b,envy,unmet,history,snapshot=s;own=list(owners)
 if a==1:own[cursor]=1-own[cursor];history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%8;history=(history+(2,))[-8:]
 elif a==3:view=1-view;history=(history+(3,))[-8:]
 elif a==4:
  utility_a=sum(v for i,v in enumerate(VALUES_A) if own[i]==0);other_a=sum(v for i,v in enumerate(VALUES_A) if own[i]==1);utility_b=sum(v for i,v in enumerate(VALUES_B) if own[i]==1);other_b=sum(v for i,v in enumerate(VALUES_B) if own[i]==0);envy=int(utility_a<other_a)+int(utility_b<other_b);unmet=int(utility_a<10)+int(utility_b<10);history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(own),cursor,view,utility_a,utility_b,envy,unmet,history)
 return tuple(own),cursor,view,utility_a,utility_b,envy,unmet,history,snapshot
for x in LEVELS:
 s=((0,1,0,1,0,1,0,1),0,0,16,16,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TABLE
  vals=VALUES_B if g.view else VALUES_A
  for i,owner in enumerate(g.owners):
   x=9+(i%4)*13;y=14+(i//4)*18;f[y:y+12,x:x+10]=TILE_A if i%2==0 else TILE_B;f[y+8:y+12,x:x+10]=OWNER_A if owner==0 else OWNER_B
   f[y+2:y+4,x+2:x+2+min(6,vals[i])]=VALUE_B if g.view else VALUE_A
   if i==g.cursor:f[y-3:y,x-1:x+11]=NEED
  f[51:55,8:8+min(10,g.utility_a)*4]=OWNER_A;f[55:59,8:8+min(10,g.utility_b)*4]=OWNER_B;f[7:10,8:8+g.envy*18]=ENVY
  if g.bad:f[1:4,18:46]=BAD
  return f
class A117(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a117",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.owners,self.cursor,self.view,self.utility_a,self.utility_b,self.envy,self.unmet,self.history,self.snapshot=((0,1,0,1,0,1,0,1),0,0,16,16,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.owners,self.cursor,self.view,self.utility_a,self.utility_b,self.envy,self.unmet,self.history,self.snapshot=advance((self.owners,self.cursor,self.view,self.utility_a,self.utility_b,self.envy,self.unmet,self.history,self.snapshot),a)
  elif a==6:
   if (self.owners,self.cursor,self.view,self.utility_a,self.utility_b,self.envy,self.unmet,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
