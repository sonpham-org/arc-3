"""a144 Group Walk -- navigate abstract pose by reducing a transformation word."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SPACE,TOKEN,WORD_A,WORD_B,INVERSE,CANCEL,GOAL,POSE,LONG=11,8,12,10,14,13,4,9,6,7
BAD=15
LEVELS=[
 {"name":"Append Transform","seq":(1,)},{"name":"Append Inverse","seq":(2,)},
 {"name":"Change Goal","seq":(3,1)},{"name":"Cancel Pair","seq":(1,2,3,4,2)},
 {"name":"Exploit Repetition","seq":(1,3,2,1,4,3,2)},{"name":"Group Walk","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def reduce_word(word):
 stack=[]
 for x in word:
  if stack and (stack[-1]+2)%4==x:stack.pop()
  else:stack.append(x)
 return tuple(stack)
def advance(s,a):
 word,goal,pose,reduced,canceled,history,snapshot=s;w=word
 if a==1:w=(w+(goal%4,))[-10:];history=(history+(1,))[-8:]
 elif a==2:w=(w+((goal+2)%4,))[-10:];history=(history+(2,))[-8:]
 elif a==3:goal=(goal+1)%4;history=(history+(3,))[-8:]
 elif a==4:r=reduce_word(w);pose=sum(r)%4;reduced=len(r);canceled=len(w)-reduced;history=(history+(4,))[-8:]
 elif a==5:snapshot=(w,goal,pose,reduced,canceled,history)
 return w,goal,pose,reduced,canceled,history,snapshot
for q in LEVELS:
 s=((),0,0,0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SPACE;pts=((31,11),(51,31),(31,51),(11,31));x,y=pts[g.pose];f[y-6:y+7,x-6:x+7]=TOKEN;gx,gy=pts[g.goal];f[gy-3:gy+4,gx-3:gx+4]=GOAL
  for i,v in enumerate(g.word):f[7:11,7+i*5:11+i*5]=WORD_A if v%2==0 else WORD_B
  f[54:58,8:8+g.canceled*6]=CANCEL;f[54:58,45:45+g.reduced*3]=LONG;f[29:34,29:34]=POSE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A144(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a144",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.word,self.goal,self.pose,self.reduced,self.canceled,self.history,self.snapshot=((),0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.word,self.goal,self.pose,self.reduced,self.canceled,self.history,self.snapshot=advance((self.word,self.goal,self.pose,self.reduced,self.canceled,self.history,self.snapshot),a)
  elif a==6:
   if (self.word,self.goal,self.pose,self.reduced,self.canceled,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
