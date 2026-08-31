"""a178 Counterexample Garden -- make the smallest edit that falsifies a growth rule."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,GARDEN,PLANT,LEAF_A,LEAF_B,EDIT,GROWTH,COUNTEREXAMPLE,BUDGET,EXCESS=15,8,7,12,14,13,10,4,11,6
BAD=9
LEVELS=[
 {"name":"Edit Leaf","seq":(1,)},{"name":"Select Leaf","seq":(2,)},
 {"name":"Advance Growth","seq":(3,1)},{"name":"Test Proposed Rule","seq":(1,2,3,4,2)},
 {"name":"Minimize Exception","seq":(1,3,2,1,4,3,2)},{"name":"Counterexample Garden","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 leaves,cursor,generation,edits,contradiction,excess,history,snapshot=s
 if a==1:leaves^=1<<cursor;edits=(edits+1)%8;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%9;history=(history+(2,))[-8:]
 elif a==3:generation=(generation+1)%5;history=(history+(3,))[-8:]
 elif a==4:predicted=(leaves.bit_count()+generation)%2;actual=((leaves&0b101010101).bit_count()+generation)%2;contradiction=int(predicted!=actual);excess=max(0,edits-1);history=(history+(4,))[-8:]
 elif a==5:snapshot=(leaves,cursor,generation,edits,contradiction,excess,history)
 return leaves,cursor,generation,edits,contradiction,excess,history,snapshot
for q in LEVELS:
 s=(0b000010000,0,0,0,0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GARDEN;f[17:55,29:35]=PLANT
  for i in range(9):
   x=10+(i%3)*17;y=10+(i//3)*14;f[y:y+10,x:x+12]=LEAF_A if (g.leaves>>i)&1 else LEAF_B
   if i==g.cursor:f[y-3:y,x:x+12]=EDIT
  f[54:58,8:8+g.edits*7]=BUDGET;f[7:10,8:32]=COUNTEREXAMPLE if g.contradiction else GROWTH;f[54:58,50:50+g.excess*2]=EXCESS
  if g.bad:f[1:4,18:46]=BAD
  return f
class A178(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a178",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.leaves,self.cursor,self.generation,self.edits,self.contradiction,self.excess,self.history,self.snapshot=(0b000010000,0,0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.leaves,self.cursor,self.generation,self.edits,self.contradiction,self.excess,self.history,self.snapshot=advance((self.leaves,self.cursor,self.generation,self.edits,self.contradiction,self.excess,self.history,self.snapshot),a)
  elif a==6:
   if (self.leaves,self.cursor,self.generation,self.edits,self.contradiction,self.excess,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
