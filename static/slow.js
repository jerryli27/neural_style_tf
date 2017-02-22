$(function() {
        image_id = "test_id"
        $("#painting_label").hide();
        $("#submit").prop("disabled",false);

        $("#submit").click( function(){
            if( !$("#background").attr("src") ){
                alert( "Please upload a content file" );
            } else {
                if( !$("#style").attr("src") ){
                    alert( "Please upload a style file" );
                }
                else {
                    colorize();
                }
            }
        });

        $('#img_pane').hide()

        $("#load_line_file").fileinput({'showUpload':false, 'previewFileType':'any'});
        $("#load_style_file").fileinput({'showUpload':false, 'previewFileType':'any'});

        //$('#line_form').on('change', 'input[type="file"]', function(e) {
        $('#load_line_file').on('change', function(e) {
          var file = e.target.files[0],
              reader = new FileReader(),
              $preview = $(".preview");

          if(file.type.indexOf("image") < 0){
            return false;
          }

          reader.onload = (function(file) {
            console.log("up content")
            return function(e) { select_src( e.target.result ); }
          })(file);

          reader.readAsDataURL(file);
        });


        $('#load_style_file').on('change', function(e) {
          var file = e.target.files[0],
              reader = new FileReader(),
              $preview = $(".preview");

          if(file.type.indexOf("image") < 0){
            return false;
          }

          reader.onload = (function(file) {
            console.log("up style")
            return function(e) { select_style( e.target.result ); }
          })(file);

          reader.readAsDataURL(file);
        });


        $("#set_line_url").click( function(){
          //currently not work 
          select_src( $("#load_line_url").val() )
        });

//--- functions

        function uniqueid(){
            var idstr=String.fromCharCode(Math.floor((Math.random()*25)+65));
            do {                
                var ascicode=Math.floor((Math.random()*42)+48);
                if (ascicode<58 || ascicode>64){
                    idstr+=String.fromCharCode(ascicode);    
                }                
            } while (idstr.length<32);
            return (idstr);
        } 

        startPaint = function(){
            $("#painting_label").show();
            $("#submit").prop("disabled",true);
            console.log("coloring start");
        }
        endPaint = function(){
            $("#painting_label").hide();
            $("#submit").prop("disabled",false);
            console.log("coloring finish");
        }

        colorize = function(){
            startPaint()
            var ajaxData = new FormData();
            ajaxData.append('line', $("#background").attr("src") );
            ajaxData.append('style', $("#style").attr("src") );
            ajaxData.append('blur', $("#blur_k").val() );
            ajaxData.append('id', image_id );
            ajaxData.append('mode','slow');
            $.ajax({
                url: "/post",
                data: ajaxData,
                cache: false,
                contentType: false,
                processData: false,
                type: 'POST',
                dataType:'json',
                complete: function(data) {
                        //location.reload();
                        console.log("uploaded")
                        var now = new Date().getTime();

                        $('#output').attr('src', '/static/images/out/'+image_id+'_0.jpg?' + now);
                        $('#output_hyperlink').attr('href', '/static/images/out/'+image_id+'_0.jpg?' + now);

//                        for (var i = 0; i < 38; i+=1) {
//                            $('#output_img_'.concat(i.toString())).attr('src', '/static/images/out/'+image_id+'_'+ i + '.jpg?' + now);
//                            $('#output_hyperlink'.concat(i.toString())).attr('href', '/static/images/out/'+image_id+'_'+ i + '.jpg?' + now);
//                        }

                        endPaint()
                }
              });
        }

        select_src = function(src){
          $("#img_pane").show(
            "fast", function(){
              image_id = uniqueid()

              $("#background").attr("src", src );
              $("#background_hyperlink").attr("href", src );
//              $("#submit").prop("disabled",true)
//              colorize();
          });
        };

        select_style = function(src){
          $("#img_pane").show(
            "fast", function(){
              image_id = uniqueid()

              $("#style").attr("src", src );
              $("#style_hyperlink").attr("href", src );
//              $("#submit").prop("disabled",true)
//              colorize();
          });
        };



});
