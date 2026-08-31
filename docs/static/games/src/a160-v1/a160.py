"""a160 Cross-Modal Category -- transfer relational structure from motion to space."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,THEATER,MOTION,STATIC,NODE_A,NODE_B,EDGE,CLASS_A,CLASS_B,TRANSFER=12,8,10,14,7,13,9,4,11,6
BAD=15
LEVELS=[
 {"name":"Change Modality","seq":(1,)},{"name":"Select Structure","seq":(2,)},
 {"name":"Assign Class","seq":(3,1)},{"name":"Map Relation Graph","seq":(1,2,3,4,2)},
 {"name":"Ignore Surface Form","seq":(1,3,2,1,4,3,2)},{"name":"Cross-Modal Category","seq":(1,2,3,1,4,2,3,1,4,3)},
]
STRUCT=(0,1,2,0,2,1)
def advance(s,a):
 modality,cursor,classes,correct,errors,history,snapshot=s;c=list(classes)
 if a==1:modality=1-modality;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:c[cursor]=1-c[cursor];history=(history+(3,))[-8:]
 elif a==4:truth=[int(x in (0,2)) for x in STRUCT];correct=sum(int(c[i]==truth[i]) for i in range(6));errors=6-correct;history=(history+(4,))[-8:]
 elif a==5:snapshot=(modality,cursor,tuple(c),correct,errors,history)
 return modality,cursor,tuple(c),correct,errors,history,snapshot
for q in LEVELS:
 s=(0,0,(1,0,1,1,1,0),6,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=THEATER;f[7:11,8:28]=MOTION if g.modality==0 else STATIC
  for i,s in enumerate(STRUCT):
   x=10+(i%3)*17;y=16+(i//3)*22;f[y:y+14,x:x+14]=NODE_A if s%2==0 else NODE_B;f[y+4:y+10,x+4:x+10]=CLASS_A if g.classes[i] else CLASS_B
   if i<5:f[y+6:y+8,x+14:min(58,x+20)]=EDGE
   if i==g.cursor:f[y-3:y,x:x+14]=TRANSFER
  f[54:58,8:8+g.correct*7]=TRANSFER;f[54:58,50:50+g.errors*2]=BAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A160(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a160",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.modality,self.cursor,self.classes,self.correct,self.errors,self.history,self.snapshot=(0,0,(1,0,1,1,1,0),6,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.modality,self.cursor,self.classes,self.correct,self.errors,self.history,self.snapshot=advance((self.modality,self.cursor,self.classes,self.correct,self.errors,self.history,self.snapshot),a)
  elif a==6:
   if (self.modality,self.cursor,self.classes,self.correct,self.errors,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
